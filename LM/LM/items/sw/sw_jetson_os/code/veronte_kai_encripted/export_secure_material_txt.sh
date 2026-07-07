#!/usr/bin/env bash
set -euo pipefail

umask 077

L4T="${L4T:-/home/ejn3@ad.embention.com/Documents/Jetson/Linux_for_Tegra_og/Linux_for_Tegra}"
HARD="${HARD:-/home/ejn3@ad.embention.com/Documents/Jetson/veronte_kai_encripted}"
KEYDIR="${KEYDIR:-$HARD/keys}"
SECUREBOOT_DIR="$HARD/secureboot_keys"
UEFI_DIR="$HARD/uefi_keys"

TS="$(date +%Y%m%d_%H%M%S)"
OUT_DIR="$HARD/backups"
OUT_TXT="$OUT_DIR/jetson_secure_material_${TS}.txt"

mkdir -p "$OUT_DIR"

require_file() {
    if [ ! -f "$1" ]; then
        echo "ERROR: missing required file: $1"
        exit 1
    fi
}

write_text_file() {
    local title="$1"
    local path="$2"

    require_file "$path"

    {
        echo
        echo "================================================================================"
        echo "$title"
        echo "PATH: $path"
        echo "SHA256: $(sha256sum "$path" | awk '{print $1}')"
        echo "SIZE: $(wc -c < "$path") bytes"
        echo "--------------------------------------------------------------------------------"
        cat "$path"
        echo
    } >> "$OUT_TXT"
}

write_base64_file() {
    local title="$1"
    local path="$2"

    require_file "$path"

    {
        echo
        echo "================================================================================"
        echo "$title"
        echo "PATH: $path"
        echo "SHA256: $(sha256sum "$path" | awk '{print $1}')"
        echo "SIZE: $(wc -c < "$path") bytes"
        echo "ENCODING: base64"
        echo "RESTORE_COMMAND:"
        echo "  base64 -d ${title}.base64 > restored_file"
        echo "--------------------------------------------------------------------------------"
        base64 -w 64 "$path"
        echo
    } >> "$OUT_TXT"
}

write_optional_text_file() {
    local title="$1"
    local path="$2"

    if [ -f "$path" ]; then
        write_text_file "$title" "$path"
    else
        {
            echo
            echo "================================================================================"
            echo "$title"
            echo "MISSING OPTIONAL FILE: $path"
        } >> "$OUT_TXT"
    fi
}

write_optional_base64_file() {
    local title="$1"
    local path="$2"

    if [ -f "$path" ]; then
        write_base64_file "$title" "$path"
    else
        {
            echo
            echo "================================================================================"
            echo "$title"
            echo "MISSING OPTIONAL FILE: $path"
        } >> "$OUT_TXT"
    fi
}

cat > "$OUT_TXT" <<EOF
JETSON SECURE MATERIAL BACKUP
Created: $(date -Is)

WARNING:
This TXT contains private keys, encryption keys and fuse material.
If leaked, your security model is compromised.
If lost after burning fuses, the Jetson may become impossible to update/reflash correctly.

Store this file only inside an encrypted container/drive, e.g. BitLocker.
Do not commit it to git.
Do not send it by email or chat.
Keep at least two offline backups.

L4T=$L4T
HARD=$HARD
KEYDIR=$KEYDIR
SECUREBOOT_DIR=$SECUREBOOT_DIR
UEFI_DIR=$UEFI_DIR
EOF

echo "[1/5] Secure Boot / fuse files"
write_text_file "rsa3k.pem" "$SECUREBOOT_DIR/rsa3k.pem"
write_text_file "fuse_rsa3k_oemk1.xml" "$SECUREBOOT_DIR/fuse_rsa3k_oemk1.xml"
write_optional_text_file "fuse_rsa3k.xml" "$SECUREBOOT_DIR/fuse_rsa3k.xml"
write_optional_base64_file "rsa3k.pubkey" "$SECUREBOOT_DIR/rsa3k.pubkey"
write_optional_base64_file "rsa3k.hash" "$SECUREBOOT_DIR/rsa3k.hash"
write_optional_text_file "pubkeyhash.log" "$SECUREBOOT_DIR/pubkeyhash.log"

echo "[2/5] EKS / encryption keys"
write_text_file "oem_k1.key" "$KEYDIR/oem_k1.key"
write_text_file "sym_t234.key" "$KEYDIR/sym_t234.key"
write_text_file "sym2_t234.key" "$KEYDIR/sym2_t234.key"
write_text_file "auth_t234.key" "$KEYDIR/auth_t234.key"
write_base64_file "eks_t234.img" "$KEYDIR/eks_t234.img"

echo "[3/5] L4T copied keys"
write_text_file "disk_enc.key" "$L4T/disk_enc.key"
write_text_file "user_encryption.key" "$L4T/user_encryption.key"
write_base64_file "bootloader_eks_t234.img" "$L4T/bootloader/eks_t234.img"

echo "[4/5] UEFI Secure Boot keys"
write_text_file "PK.key" "$UEFI_DIR/PK.key"
write_text_file "KEK.key" "$UEFI_DIR/KEK.key"
write_text_file "db_1.key" "$UEFI_DIR/db_1.key"
write_text_file "uefi_keys.conf" "$UEFI_DIR/uefi_keys.conf"

write_optional_text_file "PK.crt" "$UEFI_DIR/PK.crt"
write_optional_text_file "PK.esl" "$UEFI_DIR/PK.esl"
write_optional_text_file "KEK.crt" "$UEFI_DIR/KEK.crt"
write_optional_text_file "KEK.esl" "$UEFI_DIR/KEK.esl"
write_optional_text_file "db_1.crt" "$UEFI_DIR/db_1.crt"
write_optional_text_file "db_1.esl" "$UEFI_DIR/db_1.esl"
write_optional_text_file "UefiDefaultSecurityKeys.dts" "$UEFI_DIR/UefiDefaultSecurityKeys.dts"
write_optional_base64_file "UefiDefaultSecurityKeys.dtbo" "$UEFI_DIR/UefiDefaultSecurityKeys.dtbo"

echo "[5/5] Final checksum list"
{
    echo
    echo "================================================================================"
    echo "GLOBAL SHA256 CHECKSUMS"
    echo "--------------------------------------------------------------------------------"

    for f in \
        "$SECUREBOOT_DIR/rsa3k.pem" \
        "$SECUREBOOT_DIR/fuse_rsa3k_oemk1.xml" \
        "$SECUREBOOT_DIR/fuse_rsa3k.xml" \
        "$SECUREBOOT_DIR/rsa3k.pubkey" \
        "$SECUREBOOT_DIR/rsa3k.hash" \
        "$SECUREBOOT_DIR/pubkeyhash.log" \
        "$KEYDIR/oem_k1.key" \
        "$KEYDIR/sym_t234.key" \
        "$KEYDIR/sym2_t234.key" \
        "$KEYDIR/auth_t234.key" \
        "$KEYDIR/eks_t234.img" \
        "$L4T/disk_enc.key" \
        "$L4T/user_encryption.key" \
        "$L4T/bootloader/eks_t234.img" \
        "$UEFI_DIR/PK.key" \
        "$UEFI_DIR/KEK.key" \
        "$UEFI_DIR/db_1.key" \
        "$UEFI_DIR/uefi_keys.conf" \
        "$UEFI_DIR/PK.crt" \
        "$UEFI_DIR/PK.esl" \
        "$UEFI_DIR/KEK.crt" \
        "$UEFI_DIR/KEK.esl" \
        "$UEFI_DIR/db_1.crt" \
        "$UEFI_DIR/db_1.esl" \
        "$UEFI_DIR/UefiDefaultSecurityKeys.dts" \
        "$UEFI_DIR/UefiDefaultSecurityKeys.dtbo"
    do
        if [ -f "$f" ]; then
            sha256sum "$f"
        fi
    done
} >> "$OUT_TXT"

chmod 600 "$OUT_TXT"

echo
echo "DONE"
echo "TXT backup created:"
echo "  $OUT_TXT"
echo
echo "Size:"
ls -lh "$OUT_TXT"
