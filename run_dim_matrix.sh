#!/bin/bash
# Dimension pass matrix. One build per configuration so the toggles are audited
# in isolation; every output lands in out/dim_<variant>_<res>/ so nothing can
# touch an accepted master.
set -uo pipefail
cd "$(dirname "$0")"
B=/opt/homebrew/bin/blender
R=2400
run() {  # run <label> <extra flags...>
  local label="$1"; shift
  echo "### $label  $*"
  $B -b -noaudio --python build_lines_3d.py -- \
     --res $R --stage dim --label "$label" "$@" 2>&1 \
   | grep -E "^\[eez\] (shade|contact shadow|dof|cam drift|depth grade|back-vert|re-seated)|^\[gate\] (non-manifold|degenerate|self-inter|STRUCTURAL)|^\[eez\] dim "
}
run base
run shade05  --shade 0.5
run shade10  --shade 1.0
run dof28    --dof 2.8
run dof56    --dof 5.6
run shadow03 --shadow 0.3
run shadow06 --shadow 0.6
run grade04  --depth-grade 0.4
run sink     --shade 0.5 --dof 5.6 --shadow 0.3 --depth-grade 0.4 --cam-drift 4
echo "### drift mini-strip (low res, parallax needs motion)"
$B -b -noaudio --python build_lines_3d.py -- \
   --res 900 --stage driftstrip --label drift4 --cam-drift 4 2>&1 \
 | grep -E "cam drift|drift strip|frame 241"
