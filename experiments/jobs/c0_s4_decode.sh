#!/bin/bash
set -euo pipefail
.venv/bin/python experiments/analyse.py --study S4-val-decode --split val --arms "kmx64@fit|cos,knnx8@fit|cos,knnxd2_8@fit|cos" --refs "zero|cos,fam@fit|cos,tok@fit|cos" --decode-g --device cuda
