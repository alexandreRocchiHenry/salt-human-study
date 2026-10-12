#!/bin/bash
#SBATCH -J hx_stimuli
# Runs the stimulus generator on an aarch64 GPU node (torch is only installed there).
source /lustre/work/pdl16831/udl5a0991/workspace/Supervised_concept_SAE/wb_deb/jobs/env.sh
cd /lustre/work/pdl16831/udl5a0991/workspace/Supervised_concept_SAE/human_exp/stimuli_gen
$V make_stimuli.py "$@"
