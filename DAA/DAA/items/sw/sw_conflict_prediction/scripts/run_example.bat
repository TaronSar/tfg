@echo off

REM Resolve the project root (sw_conflict_prediction/) from the script location.
REM Uses a variable prefix so the caller's working directory is never changed.
set "_BASE=%~dp0.."

REM =====================================================================
REM ESTIMATOR MODEL
REM Set the estimator to use across all pipeline stages:
REM   cv  - Constant Velocity (6-state: position + velocity in NED)
REM   ca  - Constant Acceleration (9-state: position + velocity + acceleration in NED)
REM   cab - Constant Acceleration in Body frame (9-state: position + velocity in NED
REM         + acceleration in velocity-aligned frame: tangential, normal, vertical)
REM =====================================================================
set ESTIMATOR=cab

REM =====================================================================
REM SELECT TRUE TRAJECTORY SOURCE
REM Change the goto below to pick one of:
REM   option_caa                          - CAA gyrocopter model with rotation/displacement
REM   option_test_front_collision         - Head-on collision (both along north axis)
REM   option_test_front_parallel_miss     - Parallel near-miss (head-on with 500 ft east offset)
REM   option_test_perpendicular_collision - Perpendicular collision (north vs east at origin)
REM   option_test_perpendicular_miss      - Perpendicular miss (intruder crosses origin before ownship)
REM   option_test_chase_miss              - Chase scenario (intruder ahead, pulling away north)
REM   option_test_chase_catch             - Chase scenario (ownship catches slower intruder)
REM   option_test_circular_cross          - Ownship straight north crosses intruder's circular path
REM =====================================================================
goto option_test_circular_cross

:option_caa
python "%_BASE%\scripts\caa_to_true_trajectory.py" ^
--input "%_BASE%\examples\Gyrocopter_Data_Result.csv" ^
--ownship-id 1 ^
--intruder-id 2 ^
--ownship-rotation 30 ^
--intruder-displacement 0 4000 700 ^
--output "%_BASE%\examples\example_true_trajectory.csv"
goto pipeline

:option_test_front_collision
python "%_BASE%\scripts\generate_test_true_trajectories.py" ^
--scenario front_collision ^
--output "%_BASE%\examples\example_true_trajectory.csv"
goto pipeline

:option_test_front_parallel_miss
python "%_BASE%\scripts\generate_test_true_trajectories.py" ^
--scenario front_parallel_miss ^
--output "%_BASE%\examples\example_true_trajectory.csv"
goto pipeline

:option_test_perpendicular_collision
python "%_BASE%\scripts\generate_test_true_trajectories.py" ^
--scenario perpendicular_collision ^
--output "%_BASE%\examples\example_true_trajectory.csv"
goto pipeline

:option_test_perpendicular_miss
python "%_BASE%\scripts\generate_test_true_trajectories.py" ^
--scenario perpendicular_miss ^
--output "%_BASE%\examples\example_true_trajectory.csv"
goto pipeline

:option_test_chase_miss
python "%_BASE%\scripts\generate_test_true_trajectories.py" ^
--scenario chase_miss ^
--output "%_BASE%\examples\example_true_trajectory.csv"
goto pipeline

:option_test_chase_catch
python "%_BASE%\scripts\generate_test_true_trajectories.py" ^
--scenario chase_catch ^
--output "%_BASE%\examples\example_true_trajectory.csv"
goto pipeline

:option_test_circular_cross
python "%_BASE%\scripts\generate_test_true_trajectories.py" ^
--scenario circular_cross ^
--output "%_BASE%\examples\example_true_trajectory.csv"
goto pipeline

:pipeline
REM =====================================================================
REM PIPELINE
REM =====================================================================

REM Generate vision measurements from the true trajectory
python "%_BASE%\scripts\trajectory_to_vision.py" ^
--input "%_BASE%\examples\example_true_trajectory.csv" ^
--output "%_BASE%\examples\example_measurements.csv"

REM Run UKF tracking + conflict prediction in a single pass.
REM --save-trajectory produces the recovered intruder trajectory CSV
REM needed by the visualisation scripts below.
python "%_BASE%\scripts\conflict_prediction.py" ^
    --input "%_BASE%\examples\example_measurements.csv" ^
    --output "%_BASE%\examples\conflict_results.csv" ^
    --save-trajectory "%_BASE%\examples\example_recovered_trajectory.csv" ^
    --ownship-cylinder-height-ft 3000 ^
    --ownship-cylinder-diameter-ft 4000 ^
    --estimator %ESTIMATOR%

REM Visualize extrapolation quality as 3D surface
python "%_BASE%\scripts\visualize_extrapolation.py" ^
--ownship "%_BASE%\examples\example_measurements.csv" ^
--intruder "%_BASE%\examples\example_recovered_trajectory.csv" ^
--cylinder-height-ft 3000 ^
--cylinder-diameter-ft 4000 ^
--max-lookahead-s 60 ^
--lookahead-step-s 1 ^
--estimator %ESTIMATOR%

REM Then visualize the scenario with UKF trajectory and conflict results
python "%_BASE%\scripts\visualize_trajectories.py" ^
--true-trajectories "%_BASE%\examples\example_true_trajectory.csv" ^
--measurements "%_BASE%\examples\example_measurements.csv" ^
--interval 2 ^
--frame-step 5 ^
--estimated-intruder-trajectory "%_BASE%\examples\example_recovered_trajectory.csv" ^
--conflict-results "%_BASE%\examples\conflict_results.csv" ^
--show-uncertainty ^
--uncertainty-scale 1