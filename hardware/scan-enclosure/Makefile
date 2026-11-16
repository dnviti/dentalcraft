# Parametric scan enclosure. Parameter overrides: make all ARGS="distance=200 elevation=45"
# Profiles: ARGS="--scanner mini2 --turntable revopoint_a230_ii"
PY ?= python3
ARGS ?=

.PHONY: all build validate renders slice report clean

all: build validate renders slice report

build:
	$(PY) src/build.py $(ARGS)

validate:
	$(PY) src/validate.py $(ARGS)

renders:
	$(PY) src/render.py $(ARGS)
	$(PY) src/section.py $(ARGS)
	$(PY) src/closeups.py $(ARGS)

slice:
	$(PY) src/slice_orca.py

report:
	$(PY) src/report.py $(ARGS)

clean:
	rm -rf build
