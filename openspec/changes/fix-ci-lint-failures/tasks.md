# Tasks

## 1. C++ lint

- [ ] 1.1 Apply the project uncrustify config to `guide_robot_hardware/include/guide_robot_hardware/guide_robot_system.hpp`, `include/guide_robot_hardware/speed_conversion.hpp`, `src/guide_robot_system.cpp`; verify `colcon test --packages-select guide_robot_hardware` passes in `fabook/iros:x86-cpu`
- [ ] 1.2 Fix `guide_robot_bt_nodes/src/say_action.cpp`: add the legal/copyright header and apply uncrustify; verify `colcon test --packages-select guide_robot_bt_nodes` passes

## 2. Python lint

- [ ] 2.1 Fix flake8 E402 (import after code, lines 56–62) and pep257 D213 in `guide_robot_sonar/scripts/sonar_node_mult.py` and `sonar_mapping.py` without changing the load-bearing `sys.path` bootstrap behavior; verify `colcon test --packages-select guide_robot_sonar` passes

## 3. Full-flow verification

- [ ] 3.1 Run `colcon build` + `colcon test --return-code-on-test-failure` in `fabook/iros:x86-cpu` (with the CI pytest 8.4.2 step); verify the test phase exits 0 with no lint failures
