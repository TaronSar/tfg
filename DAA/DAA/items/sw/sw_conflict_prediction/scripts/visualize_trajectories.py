#!/usr/bin/env python3
"""
Trajectory and Vision Measurement Visualization Script

This script visualizes aircraft trajectories and the corresponding vision measurements
using matplotlib animation. It helps verify the consistency of azimuth, elevation, 
and range calculations by showing the geometric relationships over time.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.patches import FancyArrowPatch
from mpl_toolkits.mplot3d import proj3d
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import argparse
import sys
import os

from .conflict_prediction import (
    ground_truth_collision,
    classify_result,
    fn_sub_reason,
    DEFAULT_DEAD_ZONE_S,
    DEFAULT_LEAD_TIME_MARGIN_S,
    ConflictAnalyzer,
)


class Arrow3D(FancyArrowPatch):
    """3D arrow for matplotlib."""
    def __init__(self, xs, ys, zs, *args, **kwargs):
        FancyArrowPatch.__init__(self, (0,0), (0,0), *args, **kwargs)
        self._verts3d = xs, ys, zs

    def do_3d_projection(self, renderer=None):
        xs3d, ys3d, zs3d = self._verts3d
        xs, ys, zs = proj3d.proj_transform(xs3d, ys3d, zs3d, self.axes.M)
        self.set_positions((xs[0],ys[0]),(xs[1],ys[1]))
        return np.min(zs)


class TrajectoryVisualizer:
    """Visualize aircraft trajectories and vision measurements."""
    
    def __init__(self, trajectory_df: pd.DataFrame,
                 measurements_df: pd.DataFrame,
                 estimated_intruder_df: pd.DataFrame,
                 conflict_results_df: pd.DataFrame,
                 show_uncertainty: bool = False,
                 uncertainty_scale: float = 2.0,
                 title: str = None):
        """
        Initialize the visualizer.
        
        Args:
            trajectory_df: True-trajectory DataFrame
            measurements_df: Vision measurements DataFrame
            estimated_intruder_df: Estimated intruder trajectory DataFrame
            conflict_results_df: Conflict results DataFrame
            show_uncertainty: Whether to display 3D uncertainty ellipsoids
            uncertainty_scale: Sigma level for uncertainty ellipsoids (1.0=1σ, 2.0=2σ, etc.)
            title: Custom figure title (default: generic title)
        """
        self._trajectory_df = trajectory_df
        self._measurements_df = measurements_df
        self._estimated_intruder_df = estimated_intruder_df
        self._conflict_results_df = conflict_results_df
        
        # Display options
        self.show_uncertainty = show_uncertainty
        self.uncertainty_scale = uncertainty_scale
        self.title = title or 'Aircraft Trajectory and Vision Analysis'
        self.uncertainty_ellipsoids = []
        
        # 3D dynamic elements
        self.ukf_cylinder_surface = None
        self.ukf_cylinder_wireframe = None
        self.ukf_range_circle = None
        
        # Lookahead prediction visualization
        self.LOOKAHEAD_SECONDS = [15, 30, 45, 60]
        self.LOOKAHEAD_COLORS = ['#2ca02c', '#bcbd22', '#ff7f0e', '#d62728']  # green -> yellow -> orange -> red
        self.show_lookahead = False
        self.lookahead_points_2d = {}
        self.lookahead_points_3d = {}
        self.lookahead_circles_2d = {}
        self.lookahead_cylinders_3d = {}  # {dt: (surface, wireframe)}
        self.lookahead_line_2d = None
        self.lookahead_line_3d = None
        
        # Consolidated data (populated by load_and_process_data)
        self.data = None
        self.time_points = None
        self.cylinder_radius = 0
        self.cylinder_height = 0
        self.show_ukf_cylinder = False
        
        # Animation parameters
        self.current_frame = 0
        self.history_length = 50
        
    def load_and_process_data(self):
        """Validate timestamps and consolidate DataFrames into a single DataFrame."""
        print("Loading and consolidating data...")
        
        measurements = self._measurements_df.copy()
        trajectories = self._trajectory_df.copy()
        estimated_intruder = self._estimated_intruder_df.copy()
        conflict_results = self._conflict_results_df.copy()
        
        # Convert true-trajectory columns to internal names used by the visualizer
        # ownship_down_m -> ownship_up_m (sign flip)
        trajectories['ownship_up_m'] = -trajectories['ownship_down_m']
        # ownship_yaw_rad -> ownship_psi_rad
        trajectories = trajectories.rename(columns={
            'ownship_yaw_rad': 'ownship_psi_rad',
            'ownship_roll_rad': 'ownship_phi_rad',
            'ownship_pitch_rad': 'ownship_theta_rad',
            'intruder_north_m': 'true_intruder_north_m',
            'intruder_east_m': 'true_intruder_east_m',
        })
        trajectories['true_intruder_up_m'] = -trajectories['intruder_down_m']
        
        est_rename = {col: f'est_{col}' for col in estimated_intruder.columns if col != 'time'}
        estimated_intruder = estimated_intruder.rename(columns=est_rename)
        
        # Drop columns from trajectories that duplicate measurements columns
        meas_cols = set(measurements.columns)
        traj_cols_to_drop = [c for c in trajectories.columns
                             if c in meas_cols and c != 'time']
        trajectories = trajectories.drop(columns=traj_cols_to_drop)
        
        # Merge all datasets on time (inner join keeps only common timestamps)
        self.data = (measurements
                     .merge(trajectories, on='time', how='inner')
                     .merge(estimated_intruder, on='time', how='inner')
                     .merge(conflict_results, on='time', how='inner'))
        
        print(f"Merged {len(self.data)} common time points "
              f"({self.data['time'].iloc[0]:.1f}s to {self.data['time'].iloc[-1]:.1f}s)")
        
        self.time_points = self.data['time'].values
        
        # Extract cylinder dimensions
        self.cylinder_radius = self.data['ownship_cylinder_diameter_m'].iloc[0] / 2.0
        self.cylinder_height = self.data['ownship_cylinder_height_m'].iloc[0]
        
        # Check for UKF uncertainty cylinder columns (from conflict results)
        self.show_ukf_cylinder = ('radial_variance_ft2' in self.data.columns
                                  and 'down_variance_ft2' in self.data.columns)
        
        # Check for lookahead prediction columns
        self.show_lookahead = all(
            f'intruder_north_at_t_plus_{dt}' in self.data.columns
            and f'radial_variance_ft2_at_t_plus_{dt}' in self.data.columns
            for dt in self.LOOKAHEAD_SECONDS
        )
        
        print(f"Consolidated {len(self.data)} records with {len(self.data.columns)} columns")
        print(f"Cylinder: diameter={self.cylinder_radius*2:.0f} m, height={self.cylinder_height:.0f} m")
        
    def setup_plots(self):
        """Set up the matplotlib figure and subplots."""
        self.fig = plt.figure(figsize=(16, 12))
        self.fig.suptitle(self.title, fontsize=14)
        
        # Create subplots - 2 columns: left side for all 2D plots, right side for 3D plot
        gs = self.fig.add_gridspec(3, 2, height_ratios=[2, 1, 1], width_ratios=[1, 1])
        
        # 1. Top-down trajectory view (left side, top)
        self.ax_traj = self.fig.add_subplot(gs[0, 0])
        self.ax_traj.set_title('Top-Down View (North-East)')
        self.ax_traj.set_xlabel('East (ft)')
        self.ax_traj.set_ylabel('North (ft)')
        self.ax_traj.grid(True, alpha=0.3)
        self.ax_traj.set_aspect('equal', adjustable='box')
        
        # 2. 3D trajectory view (right side, spanning all rows)
        self.ax_3d = self.fig.add_subplot(gs[:, 1], projection='3d')
        self.ax_3d.set_title('3D Trajectory View')
        self.ax_3d.set_xlabel('East (ft)')
        self.ax_3d.set_ylabel('North (ft)')
        self.ax_3d.set_zlabel('Altitude (ft)')
        
        # 3. Cylindrical Distance over time (left side, middle)
        self.ax_measurements = self.fig.add_subplot(gs[1, 0])
        self.ax_measurements.set_title('Cylindrical Distance vs Time')
        self.ax_measurements.set_xlabel('Time (s)')
        self.ax_measurements.set_ylabel('Normalized Cylinder Distance')
        self.ax_measurements.grid(True, alpha=0.3)
        
        # Secondary y-axis for range (kept for compatibility but unused if no measurements)
        self.ax_range = self.ax_measurements.twinx()
        self.ax_range.set_visible(False)
        
        # 4. TCPA and Tcross over time (left side, bottom)
        self.ax_tcpa = self.fig.add_subplot(gs[2, 0])
        self.ax_tcpa.set_title('TCPA & Tcross vs Time')
        self.ax_tcpa.set_xlabel('Time (s)')
        self.ax_tcpa.set_ylabel('Lookahead (s)')
        self.ax_tcpa.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
    def create_uncertainty_ellipsoid(self, position, covariance_matrix, sigma_level=2.0):
        """
        Create a 3D uncertainty ellipsoid from position covariance matrix.
        
        Args:
            position: [north, east, up] position in metres
            covariance_matrix: 3x3 position covariance matrix
            sigma_level: Confidence level (1.0=1σ, 2.0=2σ, etc.)
            
        Returns:
            Surface plot object representing the ellipsoid
        """
        try:
            # Convert covariance from NED to NEU by flipping the down/up axis
            ned_to_neu = np.diag([1.0, 1.0, -1.0])
            cov_neu = ned_to_neu @ covariance_matrix @ ned_to_neu

            # Eigenvalue decomposition to get principal axes
            eigenvalues, eigenvectors = np.linalg.eigh(cov_neu)
            
            # Ensure positive eigenvalues (numerical stability)
            eigenvalues = np.maximum(eigenvalues, 1e-6)
            
            # Scale by eigenvalues and sigma level
            radii = sigma_level * np.sqrt(eigenvalues)
            
            # Create unit sphere points (low resolution for speed)
            u = np.linspace(0, 2 * np.pi, 12)
            v = np.linspace(0, np.pi, 8)
            x_sphere = np.outer(np.cos(u), np.sin(v))
            y_sphere = np.outer(np.sin(u), np.sin(v)) 
            z_sphere = np.outer(np.ones(np.size(u)), np.cos(v))
            
            # Transform sphere points to ellipsoid in NEU coordinates
            points_flat = np.vstack([x_sphere.ravel(), y_sphere.ravel(), z_sphere.ravel()])
            ellipsoid_points = eigenvectors @ np.diag(radii) @ points_flat
            
            # Translate to position (NEU coordinates)
            north_pos, east_pos, up_pos = position
            ellipsoid_points[0] += north_pos  # North
            ellipsoid_points[1] += east_pos   # East  
            ellipsoid_points[2] += up_pos     # Up
            
            # Reshape for matplotlib (expects [East, North, Up] order for x, y, z)
            x_ellipsoid = ellipsoid_points[1].reshape(x_sphere.shape)  # East -> x
            y_ellipsoid = ellipsoid_points[0].reshape(y_sphere.shape)  # North -> y
            z_ellipsoid = ellipsoid_points[2].reshape(z_sphere.shape)  # Up -> z
            
            # Use plot_surface for better reliability
            surface = self.ax_3d.plot_surface(x_ellipsoid, y_ellipsoid, z_ellipsoid,
                                            alpha=0.3, color='cyan', edgecolor='none')
            
            return surface
            
        except Exception as e:
            print(f"Error creating ellipsoid: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def init_animation(self):
        """Initialize animation elements."""
        # Trajectory lines (full paths)
        self.ownship_line_full, = self.ax_traj.plot([], [], 'b-', alpha=0.3, linewidth=1, label='Ownship')
        self.intruder_line_full, = self.ax_traj.plot([], [], 'r-', alpha=0.3, linewidth=1, label='Intruder')
        
        # Current trajectory segments (history trails)
        self.ownship_line, = self.ax_traj.plot([], [], 'b-', linewidth=2)
        self.intruder_line, = self.ax_traj.plot([], [], 'r-', linewidth=2)
        
        # Current positions
        self.ownship_point, = self.ax_traj.plot([], [], 'bo', markersize=10)
        self.intruder_point, = self.ax_traj.plot([], [], 'ro', markersize=10)
        
        # Line of sight
        self.los_line, = self.ax_traj.plot([], [], 'g--', linewidth=1, alpha=0.7, label='Line of Sight')
        
        # Ownship heading arrow (aircraft orientation)
        self.ownship_arrow = None
        
        # Camera direction arrow (x-body axis)
        self.camera_arrow = None
        
        # Intruder range circle
        self.intruder_range_circle = None
        
        # 3D cylinder elements
        self.intruder_cylinder_surface = None
        self.intruder_cylinder_wireframe = None
        
        # 3D elements
        self.ownship_line_3d_full, = self.ax_3d.plot([], [], [], 'b-', alpha=0.3, linewidth=1, label='Ownship')
        self.intruder_line_3d_full, = self.ax_3d.plot([], [], [], 'r-', alpha=0.3, linewidth=1, label='Intruder')
        self.ownship_point_3d, = self.ax_3d.plot([], [], [], 'bo', markersize=8)
        self.intruder_point_3d, = self.ax_3d.plot([], [], [], 'ro', markersize=8)
        
        # Estimated intruder trajectory elements
        self.ukf_line_2d_full, = self.ax_traj.plot([], [], 'm-', alpha=0.6, linewidth=1, label="Intruder's Estimate")
        self.ukf_line_3d_full, = self.ax_3d.plot([], [], [], 'm-', alpha=0.6, linewidth=1, label="Intruder's Estimate")
        self.ukf_point_2d, = self.ax_traj.plot([], [], 'mo', markersize=10, label="Intruder's Current")
        self.ukf_point_3d, = self.ax_3d.plot([], [], [], 'mo', markersize=8)
        
        # TCPA position elements
        self.tcpa_point_2d, = self.ax_traj.plot([], [], 'y*', markersize=15, alpha=0.8, label='TCPA Position', markeredgecolor='black', markeredgewidth=1)
        self.tcpa_point_3d, = self.ax_3d.plot([], [], [], 'y*', markersize=12, alpha=0.8, label='TCPA Position')
        
        # Tcross position elements
        self.tcross_point_2d, = self.ax_traj.plot([], [], 'rD', markersize=10, alpha=0.8, label='Tcross Position', markeredgecolor='black', markeredgewidth=1)
        self.tcross_point_3d, = self.ax_3d.plot([], [], [], 'rD', markersize=8, alpha=0.8, label='Tcross Position')
        
        # 3D camera direction arrow
        self.camera_arrow_3d = None
        
        # Cylindrical distance plot
        self.cyl_dist_0sigma_line, = self.ax_measurements.plot(
            self.data['time'], self.data['0_sigma_cylinder_distance_current'],
            'b-', alpha=0.7, linewidth=2, label=r'Current Distance (0$\sigma$)')
        if '1_sigma_cylinder_distance_min_lookahead' in self.data.columns:
            self.cyl_dist_lookahead_line, = self.ax_measurements.plot(
                self.data['time'], self.data['1_sigma_cylinder_distance_min_lookahead'],
                'r-', alpha=0.7, linewidth=2, label=r'Min Lookahead (1$\sigma$)')
            self.cyl_dist_lookahead_marker, = self.ax_measurements.plot([], [], 'ro', markersize=8)
        else:
            self.cyl_dist_lookahead_line = None
            self.cyl_dist_lookahead_marker = None
        self.cyl_threshold_line = self.ax_measurements.axhline(
            y=1.0, color='k', linestyle='--', alpha=0.7)
        self.cyl_dist_0sigma_marker, = self.ax_measurements.plot([], [], 'bo', markersize=8)

        # Vertical lines at the time of minimum distance
        times = self.data['time'].values
        d0 = self.data['0_sigma_cylinder_distance_current'].values
        t_min_0sigma = times[np.argmin(d0)]
        self.ax_measurements.axvline(x=t_min_0sigma, color='b', linestyle=':', alpha=0.5,
                                     label=f'Min 0$\sigma$ (t={t_min_0sigma:.1f}s)')
        # Shade time regions where current 0σ distance < 1.0
        below_one_0sigma = d0 < 1.0
        self.ax_measurements.fill_between(
            times, 0, 1, where=below_one_0sigma,
            color='blue', alpha=0.10, transform=self.ax_measurements.get_xaxis_transform())
        if '1_sigma_cylinder_distance_min_lookahead' in self.data.columns:
            d_la = self.data['1_sigma_cylinder_distance_min_lookahead'].values
            t_min_la = times[np.argmin(d_la)]
            self.ax_measurements.axvline(x=t_min_la, color='r', linestyle=':', alpha=0.5,
                                         label=f'Min 1$\sigma$ LA (t={t_min_la:.1f}s)')
            # Shade time regions where min lookahead 1σ distance < 1.0
            below_one = d_la < 1.0
            self.ax_measurements.fill_between(
                times, 0, 1, where=below_one,
                color='red', alpha=0.10, transform=self.ax_measurements.get_xaxis_transform())        
        # TCPA and Tcross plot
        self.tcpa_time_line, = self.ax_tcpa.plot(
            self.data['time'], self.data['tcpa_seconds'],
            'b-', alpha=0.7, linewidth=2, label='TCPA')
        self.tcross_time_line, = self.ax_tcpa.plot(
            self.data['time'], self.data['tcross_seconds'],
            'r-', alpha=0.7, linewidth=2, label='Tcross')
        self.tcpa_time_marker, = self.ax_tcpa.plot([], [], 'bo', markersize=8)
        self.tcross_time_marker, = self.ax_tcpa.plot([], [], 'ro', markersize=8)
        
        # Set up legends
        self.ax_traj.legend(loc='upper left', bbox_to_anchor=(1.01, 1.0), fontsize='small')
        self.ax_measurements.legend(loc='upper left')
        self.ax_tcpa.legend(loc='upper right')
        self.ax_3d.legend(loc='upper left', bbox_to_anchor=(0.0, 1.0), fontsize='small', borderaxespad=0)
        
        # Plot full trajectories once (they don't change during animation)
        self.ownship_line_full.set_data(self.data['ownship_east_m'], self.data['ownship_north_m'])
        self.intruder_line_full.set_data(self.data['true_intruder_east_m'], self.data['true_intruder_north_m'])
        self.ownship_line_3d_full.set_data_3d(self.data['ownship_east_m'], self.data['ownship_north_m'], self.data['ownship_up_m'])
        self.intruder_line_3d_full.set_data_3d(self.data['true_intruder_east_m'], self.data['true_intruder_north_m'], self.data['true_intruder_up_m'])
        
        # Plot estimated intruder trajectory
        self.ukf_line_2d_full.set_data(self.data['est_intruder_east_m'], self.data['est_intruder_north_m'])
        self.ukf_line_3d_full.set_data_3d(self.data['est_intruder_east_m'], self.data['est_intruder_north_m'], -self.data['est_intruder_down_m'])
        
        # Add intruder range circle
        circle = plt.Circle((0, 0), self.cylinder_radius, 
                          fill=False, color='darkcyan', alpha=0.8, linewidth=2, linestyle='--')
        self.intruder_range_circle = self.ax_traj.add_patch(circle)
        
        # Initialize 3D cylinder elements to None for first frame
        self.intruder_cylinder_surface = None
        self.intruder_cylinder_wireframe = None
        
        # UKF uncertainty cylinder around intruder (dynamic size)
        if self.show_ukf_cylinder:
            circle_ukf = plt.Circle((0, 0), 1,
                                   fill=False, color='magenta', alpha=0.6, linewidth=2, linestyle=':')
            self.ukf_range_circle = self.ax_traj.add_patch(circle_ukf)
        self.ukf_cylinder_surface = None
        self.ukf_cylinder_wireframe = None
        
        # Lookahead prediction elements
        if self.show_lookahead:
            # Connecting line from current estimate through lookahead points
            self.lookahead_line_2d, = self.ax_traj.plot([], [], '--', color='gray', alpha=0.5, linewidth=1)
            self.lookahead_line_3d, = self.ax_3d.plot([], [], [], '--', color='gray', alpha=0.5, linewidth=1)
            for dt, color in zip(self.LOOKAHEAD_SECONDS, self.LOOKAHEAD_COLORS):
                # 2D predicted position marker
                self.lookahead_points_2d[dt], = self.ax_traj.plot(
                    [], [], 'o', color=color, markersize=7, alpha=0.8,
                    markeredgecolor='black', markeredgewidth=0.5,
                    label=f't+{dt}s')
                # 3D predicted position marker
                self.lookahead_points_3d[dt], = self.ax_3d.plot(
                    [], [], [], 'o', color=color, markersize=5, alpha=0.8)
                # 2D uncertainty circle
                circle_la = plt.Circle((0, 0), 1, fill=False, color=color,
                                       alpha=0.5, linewidth=1.5, linestyle=':')
                self.lookahead_circles_2d[dt] = self.ax_traj.add_patch(circle_la)
                circle_la.set_visible(False)
                # 3D cylinders initialized to None (created dynamically)
                self.lookahead_cylinders_3d[dt] = (None, None)
        
        # Transient 3D artists that are recreated every frame (wireframes, surfaces, arrows).
        # Tracked here for reliable bulk removal so nothing leaks into the axes.
        self._transient_3d = []
        
        # Text for current values - positioned in figure margins to avoid overlap
        self.time_text = self.fig.text(0.02, 0.98, '', transform=self.fig.transFigure, 
                                      verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat'))
        self.measurement_text = self.fig.text(0.02, 0.90, '', transform=self.fig.transFigure,
                                             verticalalignment='top', bbox=dict(boxstyle='round', facecolor='lightblue'))
        
        return (self.ownship_line, self.intruder_line, self.ownship_point, self.intruder_point, 
                self.los_line, self.time_text, self.measurement_text)
    
    def _animate_mapped(self, anim_frame):
        """Map animation frame index to data index and delegate."""
        try:
            return self.animate(self._frame_indices[anim_frame])
        except Exception as e:
            import traceback
            print(f"\n*** ANIMATION ERROR at anim_frame={anim_frame}, "
                  f"data_idx={self._frame_indices[anim_frame]}: {e}")
            traceback.print_exc()
            raise

    def animate(self, frame):
        """Animation function called for each frame."""
        if frame >= len(self.time_points):
            return self.init_animation()[0:5]
        
        # Remove every transient 3D artist created in the previous frame.
        for artist in self._transient_3d:
            artist.remove()
        self._transient_3d.clear()
        
        current_time = self.time_points[frame]
        
        # Get trajectory history for trails
        start_idx = max(0, frame - self.history_length)
        end_idx = frame + 1
        history = self.data.iloc[start_idx:end_idx]
        
        # Ownship trajectory trail
        self.ownship_line.set_data(history['ownship_east_m'], history['ownship_north_m'])
        
        # Intruder trajectory trail  
        self.intruder_line.set_data(history['true_intruder_east_m'], history['true_intruder_north_m'])
        
        # Current row from consolidated data
        row = self.data.iloc[frame]
        
        self.ownship_point.set_data([row['ownship_east_m']], [row['ownship_north_m']])
        self.intruder_point.set_data([row['true_intruder_east_m']], [row['true_intruder_north_m']])
        
        # Line of sight
        self.los_line.set_data([row['ownship_east_m'], row['true_intruder_east_m']], 
                              [row['ownship_north_m'], row['true_intruder_north_m']])
        
        # Update ownship heading and camera direction arrows
        if self.ownship_arrow:
            self.ownship_arrow.remove()
        if self.camera_arrow:
            self.camera_arrow.remove()
        
        # Update estimated intruder current position
        self.ukf_point_2d.set_data([row['est_intruder_east_m']], [row['est_intruder_north_m']])
        self.ukf_point_3d.set_data_3d([row['est_intruder_east_m']], [row['est_intruder_north_m']], [-row['est_intruder_down_m']])
        
        # Update uncertainty ellipsoid if enabled
        if self.show_uncertainty:
            # Extract position covariance matrix (3x3 upper-left of P matrix)
            pos_cov = np.array([
                [row['est_P_00'], row['est_P_01'], row['est_P_02']],
                [row['est_P_01'], row['est_P_11'], row['est_P_12']],
                [row['est_P_02'], row['est_P_12'], row['est_P_22']]
            ])
            
            # Create uncertainty ellipsoid (tracked in _transient_3d)
            # Skip if any principal radius exceeds the visible axis span.
            eigvals = np.linalg.eigvalsh(pos_cov)
            max_radius = self.uncertainty_scale * np.sqrt(max(eigvals.max(), 0))
            if max_radius <= self._max_draw_radius:
                position = [row['est_intruder_north_m'], row['est_intruder_east_m'], -row['est_intruder_down_m']]
                ellipsoid = self.create_uncertainty_ellipsoid(position, pos_cov, self.uncertainty_scale)
                if ellipsoid is not None:
                    self._transient_3d.append(ellipsoid)
            else:
                print(f'[frame {frame}] Skipping ellipsoid: radius {max_radius:.0f} m > axis span {self._max_draw_radius:.0f} m')
        
        # Update UKF uncertainty cylinder around intruder
        if self.show_ukf_cylinder:
            radial_std = np.sqrt(row['radial_variance_ft2']) * self.uncertainty_scale
            down_std = np.sqrt(row['down_variance_ft2']) * self.uncertainty_scale
            ukf_east = row['est_intruder_east_m']
            ukf_north = row['est_intruder_north_m']
            ukf_up = -row['est_intruder_down_m']
            
            # Skip if the radius exceeds the visible axis span
            if radial_std <= self._max_draw_radius:
                # Update 2D circle
                if self.ukf_range_circle is not None:
                    self.ukf_range_circle.center = (ukf_east, ukf_north)
                    self.ukf_range_circle.set_radius(radial_std)
                    self.ukf_range_circle.set_visible(True)
                
                # Update 3D cylinder (tracked in _transient_3d)
                cyl_pos = {'east_m': ukf_east, 'north_m': ukf_north, 'up_m': ukf_up}
                _, wireframe = self._draw_3d_cylinder_generic(
                    cyl_pos, radial_std, down_std * 2, color='magenta')
                if wireframe is not None:
                    self._transient_3d.append(wireframe)
            else:
                if self.ukf_range_circle is not None:
                    self.ukf_range_circle.set_visible(False)
                print(f'[frame {frame}] Skipping UKF cylinder: radial_std {radial_std:.0f} m > axis span {self._max_draw_radius:.0f} m')
        
        # Update lookahead predicted positions and uncertainty cylinders
        if self.show_lookahead:
            line_east = [row['est_intruder_east_m']]
            line_north = [row['est_intruder_north_m']]
            line_up = [-row['est_intruder_down_m']]
            for dt, color in zip(self.LOOKAHEAD_SECONDS, self.LOOKAHEAD_COLORS):
                la_east = row[f'intruder_east_at_t_plus_{dt}']
                la_north = row[f'intruder_north_at_t_plus_{dt}']
                la_up = -row[f'intruder_down_at_t_plus_{dt}']
                rad_std = np.sqrt(row[f'radial_variance_ft2_at_t_plus_{dt}']) * self.uncertainty_scale
                dn_std = np.sqrt(row[f'down_variance_ft2_at_t_plus_{dt}']) * self.uncertainty_scale
                line_east.append(la_east)
                line_north.append(la_north)
                line_up.append(la_up)
                # 2D point
                self.lookahead_points_2d[dt].set_data([la_east], [la_north])
                # 3D point
                self.lookahead_points_3d[dt].set_data_3d([la_east], [la_north], [la_up])
                # Skip uncertainty geometry if radius exceeds visible axis span
                if rad_std <= self._max_draw_radius:
                    # 2D uncertainty circle
                    self.lookahead_circles_2d[dt].center = (la_east, la_north)
                    self.lookahead_circles_2d[dt].set_radius(rad_std)
                    self.lookahead_circles_2d[dt].set_visible(True)
                    # 3D uncertainty cylinder (tracked in _transient_3d)
                    cyl_pos = {'east_m': la_east, 'north_m': la_north, 'up_m': la_up}
                    _, wireframe = self._draw_3d_cylinder_generic(
                        cyl_pos, rad_std, dn_std * 2, color=color)
                    if wireframe is not None:
                        self._transient_3d.append(wireframe)
                else:
                    self.lookahead_circles_2d[dt].set_visible(False)
                    print(f'[frame {frame}] Skipping t+{dt}s cylinder: radial_std {rad_std:.2e} m > axis span {self._max_draw_radius:.0f} m')
            # Update connecting lines
            self.lookahead_line_2d.set_data(line_east, line_north)
            self.lookahead_line_3d.set_data_3d(line_east, line_north, line_up)
        
        # Update TCPA position
        tcpa_altitude = -row['intruder_down_at_tcpa']
        self.tcpa_point_2d.set_data([row['intruder_east_at_tcpa']], [row['intruder_north_at_tcpa']])
        self.tcpa_point_3d.set_data_3d([row['intruder_east_at_tcpa']], [row['intruder_north_at_tcpa']], [tcpa_altitude])
        
        # Update Tcross position (hide if NaN)
        if not np.isnan(row['intruder_down_at_tcross']):
            tcross_altitude = -row['intruder_down_at_tcross']
            self.tcross_point_2d.set_data([row['intruder_east_at_tcross']], [row['intruder_north_at_tcross']])
            self.tcross_point_3d.set_data_3d([row['intruder_east_at_tcross']], [row['intruder_north_at_tcross']], [tcross_altitude])
        else:
            self.tcross_point_2d.set_data([], [])
            self.tcross_point_3d.set_data_3d([], [], [])
        
        # Update intruder range circle position (centered on ownship position)
        self.intruder_range_circle.center = (row['ownship_east_m'], row['ownship_north_m'])
        
        # Draw heading arrow (aircraft body orientation, lighter blue)
        arrow_length = 150
        heading = row['ownship_psi_rad']
        arrow_end_east = row['ownship_east_m'] + arrow_length * np.sin(heading)
        arrow_end_north = row['ownship_north_m'] + arrow_length * np.cos(heading)
        
        self.ownship_arrow = self.ax_traj.arrow(row['ownship_east_m'], row['ownship_north_m'],
                                           arrow_end_east - row['ownship_east_m'],
                                           arrow_end_north - row['ownship_north_m'],
                                           head_width=20, head_length=15, fc='lightblue', ec='blue', alpha=0.6, linewidth=1)
        
        # Draw camera direction arrow (x-body axis, red for visibility)
        camera_length = 2000
        camera_end_east = row['ownship_east_m'] + camera_length * np.sin(heading)
        camera_end_north = row['ownship_north_m'] + camera_length * np.cos(heading)
        
        self.camera_arrow = self.ax_traj.arrow(row['ownship_east_m'], row['ownship_north_m'],
                                              camera_end_east - row['ownship_east_m'],
                                              camera_end_north - row['ownship_north_m'],
                                              head_width=30, head_length=25, fc='red', ec='darkred', alpha=0.8, linewidth=2)
        
        # Update 3D current positions only (full trajectories already plotted in init)
        self.ownship_point_3d.set_data_3d([row['ownship_east_m']], [row['ownship_north_m']], [row['ownship_up_m']])
        self.intruder_point_3d.set_data_3d([row['true_intruder_east_m']], [row['true_intruder_north_m']], [row['true_intruder_up_m']])
        
        # Update 3D cylinder on ownship position (tracked in _transient_3d)
        cylinder_pos = {
            'east_m': row['ownship_east_m'],
            'north_m': row['ownship_north_m'],
            'up_m': row['ownship_up_m']
        }
        self._draw_3d_cylinder(cylinder_pos)
        
        # 3D camera direction arrow (x-body axis, tracked in _transient_3d)
        camera_length_3d = 3000
        camera_end_east_3d = row['ownship_east_m'] + camera_length_3d * np.sin(heading)
        camera_end_north_3d = row['ownship_north_m'] + camera_length_3d * np.cos(heading)
        camera_end_up_3d = row['ownship_up_m']
        
        arrow_3d = Arrow3D([row['ownship_east_m'], camera_end_east_3d],
                           [row['ownship_north_m'], camera_end_north_3d],
                           [row['ownship_up_m'], camera_end_up_3d],
                           mutation_scale=20, lw=3, arrowstyle="-|>", color="red", alpha=0.8)
        self.ax_3d.add_artist(arrow_3d)
        self._transient_3d.append(arrow_3d)
        
        # Update current position markers on cylinder distance plot
        self.cyl_dist_0sigma_marker.set_data([current_time], [row['0_sigma_cylinder_distance_current']])
        if self.cyl_dist_lookahead_marker is not None and '1_sigma_cylinder_distance_min_lookahead' in row.index:
            self.cyl_dist_lookahead_marker.set_data([current_time], [row['1_sigma_cylinder_distance_min_lookahead']])
        
        # Update current point on TCPA/tcross plot
        self.tcpa_time_marker.set_data([current_time], [row['tcpa_seconds']])
        if not np.isnan(row['tcross_seconds']):
            self.tcross_time_marker.set_data([current_time], [row['tcross_seconds']])
        else:
            self.tcross_time_marker.set_data([], [])
        
        # Update text displays
        self.time_text.set_text(f'Time: {current_time:.1f} s\nFrame: {frame+1}/{len(self.time_points)}')
        
        self.measurement_text.set_text(
            f'Azimuth: {np.degrees(row["azimuth_rad"]):.1f}°\n'
            f'Elevation: {np.degrees(row["elevation_rad"]):.1f}°\n'
            f'Range: {row["range_m"]:.0f} m'
        )
        
        return (self.ownship_line, self.intruder_line, self.ownship_point, self.intruder_point, 
                self.los_line, self.time_text, self.measurement_text)
    
    def _draw_3d_cylinder_generic(self, pos, radius, height, color='cyan'):
        """Draw a 3D cylinder at the given position and return (surface, wireframe)."""
        theta = np.linspace(0, 2*np.pi, 16)
        z = np.linspace(-height/2, height/2, 4)
        theta_mesh, z_mesh = np.meshgrid(theta, z)
        
        x_cyl = radius * np.cos(theta_mesh) + pos['east_m']
        y_cyl = radius * np.sin(theta_mesh) + pos['north_m']
        z_cyl = z_mesh + pos['up_m']
        
        wireframe = self.ax_3d.plot_wireframe(
            x_cyl, y_cyl, z_cyl,
            alpha=0.3, color=color, linewidth=0.5, zorder=11
        )
        return None, wireframe
    
    def _draw_3d_cylinder(self, aircraft_pos):
        """Draw the ownship 3D cylinder at the aircraft position."""
        _, wireframe = self._draw_3d_cylinder_generic(
            aircraft_pos, self.cylinder_radius, self.cylinder_height, color='darkcyan')
        if wireframe is not None:
            self._transient_3d.append(wireframe)
    
    def set_axis_limits(self):
        """Set appropriate axis limits based on data."""
        # 2D trajectory limits
        east_parts = [self.data['ownship_east_m'], self.data['true_intruder_east_m'],
                      self.data['est_intruder_east_m'], self.data['intruder_east_at_tcpa'],
                      self.data['intruder_east_at_tcross'].dropna()]
        north_parts = [self.data['ownship_north_m'], self.data['true_intruder_north_m'],
                       self.data['est_intruder_north_m'], self.data['intruder_north_at_tcpa'],
                       self.data['intruder_north_at_tcross'].dropna()]
        up_parts = [self.data['ownship_up_m'].values, self.data['true_intruder_up_m'].values,
                    -self.data['est_intruder_down_m'].values, -self.data['intruder_down_at_tcpa'].values,
                    -self.data['intruder_down_at_tcross'].dropna().values]
        if self.show_lookahead:
            for dt in self.LOOKAHEAD_SECONDS:
                east_parts.append(self.data[f'intruder_east_at_t_plus_{dt}'])
                north_parts.append(self.data[f'intruder_north_at_t_plus_{dt}'])
                up_parts.append(-self.data[f'intruder_down_at_t_plus_{dt}'].values)
        all_east = np.concatenate(east_parts)
        all_north = np.concatenate(north_parts)
        all_up = np.concatenate(up_parts)
        
        east_range = all_east.max() - all_east.min()
        north_range = all_north.max() - all_north.min()
        # Ensure a minimum span so the plot isn't degenerate on collinear trajectories
        min_span = max(east_range, north_range) * 0.1
        min_span = max(min_span, 1000.0)
        east_margin = max(east_range * 0.1, min_span)
        north_margin = max(north_range * 0.1, min_span)
        
        self.ax_traj.set_xlim(all_east.min() - east_margin, all_east.max() + east_margin)
        self.ax_traj.set_ylim(all_north.min() - north_margin, all_north.max() + north_margin)
        
        # 3D limits - ensure cylinder is visible
        up_margin = (all_up.max() - all_up.min()) * 0.1
        up_margin = max(up_margin, self.cylinder_height)
        
        x_min, x_max = all_east.min() - east_margin, all_east.max() + east_margin
        y_min, y_max = all_north.min() - north_margin, all_north.max() + north_margin
        z_min, z_max = all_up.min() - up_margin, all_up.max() + up_margin
        
        # Ensure cylinder dimensions are visible in limits
        cylinder_margin = max(self.cylinder_radius, self.cylinder_height / 2)
        x_min = min(x_min, -cylinder_margin)
        x_max = max(x_max, cylinder_margin)
        y_min = min(y_min, -cylinder_margin)
        y_max = max(y_max, cylinder_margin)
        z_min = min(z_min, all_up.min() - self.cylinder_height)
        z_max = max(z_max, all_up.max() + self.cylinder_height)
        
        # Enforce equal scale on all 3D axes so spheres don't look like ellipsoids
        max_range = max(x_max - x_min, y_max - y_min, z_max - z_min)
        x_mid = (x_min + x_max) / 2
        y_mid = (y_min + y_max) / 2
        z_mid = (z_min + z_max) / 2
        self.ax_3d.set_xlim(x_mid - max_range / 2, x_mid + max_range / 2)
        self.ax_3d.set_ylim(y_mid - max_range / 2, y_mid + max_range / 2)
        self.ax_3d.set_zlim(z_mid - max_range / 2, z_mid + max_range / 2)
        self.ax_3d.set_box_aspect([1, 1, 1])
        
        # Maximum sensible radius for uncertainty geometry.  Anything larger
        # than the visible axis span is off-screen and would choke the renderer.
        self._max_draw_radius = max_range
        
        # Cylinder distance plot limits
        time_range = self.data['time']
        self.ax_measurements.set_xlim(time_range.min(), time_range.max())
        
        cyl_0sigma_vals = self.data['0_sigma_cylinder_distance_current']
        cyl_vals = self.data['1_sigma_cylinder_distance_current']
        cyl_tcpa_vals = self.data['0_sigma_cylinder_distance_at_tcpa']
        all_cyl = pd.concat([cyl_0sigma_vals, cyl_vals, cyl_tcpa_vals])
        if '1_sigma_cylinder_distance_min_lookahead' in self.data.columns:
            all_cyl = pd.concat([all_cyl, self.data['1_sigma_cylinder_distance_min_lookahead']])
        ymin = max(all_cyl.min() * 0.9, 0)
        ymax = all_cyl.max() * 1.1
        self.ax_measurements.set_ylim(ymin, ymax)
        
        # TCPA/tcross plot limits
        self.ax_tcpa.set_xlim(time_range.min(), time_range.max())
        tcpa_vals = self.data['tcpa_seconds']
        tcross_vals = self.data['tcross_seconds'].dropna()
        all_lookahead = pd.concat([tcpa_vals, tcross_vals])
        self.ax_tcpa.set_ylim(max(all_lookahead.min() * 0.9, 0), all_lookahead.max() * 1.1)
    
    def run_animation(self, interval=50, frame_step=1, save_file=None):
        """Run the animation."""
        self.setup_plots()
        self.set_axis_limits()
        
        # Build the list of data indices to render
        frame_indices = list(range(0, len(self.time_points), frame_step))
        # Always include the very last data point
        if frame_indices[-1] != len(self.time_points) - 1:
            frame_indices.append(len(self.time_points) - 1)
        self._frame_indices = frame_indices
        print(f"Animating {len(frame_indices)} frames (step={frame_step}) out of {len(self.time_points)} data points")
        
        # Create animation
        anim = animation.FuncAnimation(
            self.fig, self._animate_mapped, init_func=self.init_animation,
            frames=len(frame_indices), interval=interval, blit=False, repeat=False)
        
        if save_file:
            print(f"Saving animation to {save_file}...")
            anim.save(save_file, writer='pillow', fps=20)
            print("Animation saved!")
        
        plt.show()
        return anim


def main():
    """Main function to run the visualization."""
    parser = argparse.ArgumentParser(description='Visualize aircraft trajectories and vision measurements')
    
    parser.add_argument('--true-trajectories', required=True,
                      help='CSV file with true aircraft trajectories (already transformed)')
    parser.add_argument('--measurements', '-m', required=True,
                      help='Input CSV file with vision measurements')
    # Animation and cylinder parameters
    parser.add_argument('--interval', type=int, default=50,
                      help='Animation interval in milliseconds (default: 50)')
    parser.add_argument('--frame-step', type=int, default=1,
                      help='Only render every Nth data point (default: 1, i.e. all frames)')
    parser.add_argument('--save', type=str,
                      help='Save animation as GIF file (optional)')
    
    # UKF trajectory visualization
    parser.add_argument('--estimated-intruder-trajectory', type=str, required=True,
                      help='Estimated intruder trajectory CSV file (required)')
    parser.add_argument('--show-uncertainty', action='store_true',
                      help='Show 3D uncertainty ellipsoids for estimated intruder position')
    parser.add_argument('--uncertainty-scale', type=float, default=2.0,
                      help='Uncertainty ellipsoid scale factor (1.0=1σ, 2.0=2σ, 3.0=3σ, default: 2.0)')
    
    # TCPA conflict results visualization
    parser.add_argument('--conflict-results', type=str, required=True,
                      help='Conflict results CSV file for TCPA position visualization')

    
    args = parser.parse_args()
    
    # Validate inputs
    for label, path in [('True trajectories', args.true_trajectories),
                        ('Measurements', args.measurements),
                        ('Estimated intruder trajectory', args.estimated_intruder_trajectory),
                        ('Conflict results', args.conflict_results)]:
        if not os.path.exists(path):
            print(f"Error: {label} file '{path}' not found")
            sys.exit(1)
    
    try:
        # Read CSVs and pass DataFrames to the visualizer
        trajectory_df = pd.read_csv(args.true_trajectories)
        measurements_df = pd.read_csv(args.measurements)
        estimated_intruder_df = pd.read_csv(args.estimated_intruder_trajectory)
        conflict_results_df = pd.read_csv(args.conflict_results)

        # --- Auto-compute TP/FP/TN/FN classification title ---
        cyl_h = conflict_results_df['ownship_cylinder_height_m'].iloc[0]
        cyl_d = conflict_results_df['ownship_cylinder_diameter_m'].iloc[0]
        lookahead_s = max(ConflictAnalyzer.LOOKAHEAD_SECONDS)

        gt = ground_truth_collision(trajectory_df, cyl_h, cyl_d)
        gt_coll = gt['collision']
        collision_time = gt['collision_time']

        # Detection: first time the 1σ min-lookahead distance < 1.0
        dist_col = conflict_results_df['1_sigma_cylinder_distance_min_lookahead']
        alert_mask = dist_col < 1.0
        if alert_mask.any():
            det_time = conflict_results_df.loc[alert_mask.idxmax(), 'time']
            detected = True
        else:
            det_time = float('nan')
            detected = False

        lead = collision_time - det_time if (gt_coll and detected) else float('nan')

        label = classify_result(gt_coll, detected, lead, lookahead_s)
        _CM_LABELS = {
            'TP': 'TRUE POSITIVE', 'FP': 'FALSE POSITIVE',
            'TN': 'TRUE NEGATIVE', 'FN': 'FALSE NEGATIVE',
        }
        cm_label = _CM_LABELS[label]
        if label == 'FN':
            reason = fn_sub_reason(detected, lead, lookahead_s)
            if reason:
                cm_label += f' ({reason})'

        max_lead = lookahead_s + DEFAULT_LEAD_TIME_MARGIN_S
        lead_str = f'{lead:.1f}s (max {max_lead:.0f})' if not np.isnan(lead) else 'N/A'
        title = (f'[{cm_label}]  —  '
                 f'GT collision: {gt_coll}  |  DAA detected: {detected}  |  lead: {lead_str}')

        visualizer = TrajectoryVisualizer(
            trajectory_df=trajectory_df,
            measurements_df=measurements_df,
            estimated_intruder_df=estimated_intruder_df,
            conflict_results_df=conflict_results_df,
            show_uncertainty=args.show_uncertainty,
            uncertainty_scale=args.uncertainty_scale,
            title=title,
        )
        
        visualizer.load_and_process_data()
        visualizer.run_animation(interval=args.interval, frame_step=args.frame_step, save_file=args.save)
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()