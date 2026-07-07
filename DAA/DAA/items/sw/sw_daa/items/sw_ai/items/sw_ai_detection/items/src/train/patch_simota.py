import torch
import torch.nn.functional as F
from mmdet.models.task_modules.assigners.sim_ota_assigner import (  # type: ignore[reportMissingImports]
    EPS,
    INF,
    AssignResult,
    SimOTAAssigner,
)


# ------------------------------------------------------------------
# Patch 1: Full assign() replacement.
# The only change vs upstream is replacing F.binary_cross_entropy
# with F.binary_cross_entropy_with_logits so the CUDA kernel never
# asserts on out-of-range / NaN inputs.
# ------------------------------------------------------------------
def safe_assign(self, pred_instances, gt_instances, gt_instances_ignore=None, **kwargs):
    """Patched ``SimOTAAssigner.assign`` using numerically stable BCE."""
    gt_bboxes = gt_instances.bboxes
    gt_labels = gt_instances.labels
    num_gt = gt_bboxes.size(0)

    decoded_bboxes = pred_instances.bboxes
    pred_scores = pred_instances.scores
    priors = pred_instances.priors
    num_bboxes = decoded_bboxes.size(0)

    assigned_gt_inds = decoded_bboxes.new_full((num_bboxes,), 0, dtype=torch.long)
    if num_gt == 0 or num_bboxes == 0:
        max_overlaps = decoded_bboxes.new_zeros((num_bboxes,))
        assigned_labels = decoded_bboxes.new_full((num_bboxes,), -1, dtype=torch.long)
        return AssignResult(num_gt, assigned_gt_inds, max_overlaps, labels=assigned_labels)

    valid_mask, is_in_boxes_and_center = self.get_in_gt_and_in_center_info(priors, gt_bboxes)
    valid_decoded_bbox = decoded_bboxes[valid_mask]
    valid_pred_scores = pred_scores[valid_mask]
    num_valid = valid_decoded_bbox.size(0)
    if num_valid == 0:
        max_overlaps = decoded_bboxes.new_zeros((num_bboxes,))
        assigned_labels = decoded_bboxes.new_full((num_bboxes,), -1, dtype=torch.long)
        return AssignResult(num_gt, assigned_gt_inds, max_overlaps, labels=assigned_labels)

    pairwise_ious = self.iou_calculator(valid_decoded_bbox, gt_bboxes)
    iou_cost = -torch.log(pairwise_ious + EPS)

    gt_onehot_label = (
        F.one_hot(gt_labels.to(torch.int64), pred_scores.shape[-1])
        .float()
        .unsqueeze(0)
        .repeat(num_valid, 1, 1)
    )

    valid_pred_scores = valid_pred_scores.unsqueeze(1).repeat(1, num_gt, 1)

    # --- KEY FIX: use binary_cross_entropy_with_logits ---
    # Convert probabilities back to logits so BCE-with-logits is stable.
    with torch.cuda.amp.autocast(enabled=False):
        vps = valid_pred_scores.to(dtype=torch.float32).clamp(1e-7, 1.0 - 1e-7)
        logits = torch.log(vps / (1.0 - vps))
        cls_cost = (
            F.binary_cross_entropy_with_logits(
                logits,
                gt_onehot_label,
                reduction="none",
            )
            .sum(-1)
            .to(dtype=valid_pred_scores.dtype)
        )

    cost_matrix = (
        cls_cost * self.cls_weight + iou_cost * self.iou_weight + (~is_in_boxes_and_center) * INF
    )

    matched_pred_ious, matched_gt_inds = self.dynamic_k_matching(
        cost_matrix, pairwise_ious, num_gt, valid_mask
    )

    assigned_gt_inds[valid_mask] = matched_gt_inds + 1
    assigned_labels = assigned_gt_inds.new_full((num_bboxes,), -1)
    assigned_labels[valid_mask] = gt_labels[matched_gt_inds].long()
    max_overlaps = assigned_gt_inds.new_full((num_bboxes,), -INF, dtype=torch.float32)
    max_overlaps[valid_mask] = matched_pred_ious
    return AssignResult(num_gt, assigned_gt_inds, max_overlaps, labels=assigned_labels)


SimOTAAssigner.assign = safe_assign
print("[patch_simota] Patched SimOTAAssigner.assign (BCE_with_logits)")

# ------------------------------------------------------------------
# Patch 2: Convert dynamic_ks tensor to int for torch.topk().
# ------------------------------------------------------------------


def safe_dynamic_k_matching(
    self, cost: torch.Tensor, pairwise_ious: torch.Tensor, num_gt: int, valid_mask: torch.Tensor
):
    """Monkey-patched dynamic_k_matching that converts dynamic_k tensor to int"""
    matching_matrix = torch.zeros_like(cost, dtype=torch.uint8)

    # select candidate topk ious for dynamic-k calculation
    candidate_topk = min(self.candidate_topk, pairwise_ious.size(0))
    topk_ious, _ = torch.topk(pairwise_ious, candidate_topk, dim=0)

    # calculate dynamic k for each gt
    dynamic_ks = torch.clamp(topk_ious.sum(0).int(), min=1)
    pos_idx = None
    for gt_idx in range(num_gt):
        k = int(dynamic_ks[gt_idx].item())
        k = min(k, cost.size(0))

        _, pos_idx = torch.topk(cost[:, gt_idx], k=k, largest=False)
        pos_idx = pos_idx.clamp(0, cost.size(0) - 1)

        matching_matrix[:, gt_idx][pos_idx] = 1

    del topk_ious, dynamic_ks, pos_idx

    prior_match_gt_mask = matching_matrix.sum(1) > 1
    if prior_match_gt_mask.sum() > 0:
        _, cost_argmin = torch.min(cost[prior_match_gt_mask, :], dim=1)
        matching_matrix[prior_match_gt_mask, :] *= 0
        matching_matrix[prior_match_gt_mask, cost_argmin] = 1

    # get foreground mask inside box and center prior
    fg_mask_inboxes = matching_matrix.sum(1) > 0
    valid_mask[valid_mask.clone()] = fg_mask_inboxes

    matched_gt_inds = matching_matrix[fg_mask_inboxes, :].argmax(1)
    matched_pred_ious = (matching_matrix * pairwise_ious).sum(1)[fg_mask_inboxes]

    return matched_pred_ious, matched_gt_inds


# Apply the monkey patch
SimOTAAssigner.dynamic_k_matching = safe_dynamic_k_matching
