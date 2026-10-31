#!/bin/sh
set -eu
INPUT=/build/inputs
WORK=/build/work
mkdir -p "$WORK" /build/wheels /build/raw-wheels
cd /build
sha256sum -c "$INPUT/SHA256SUMS"
mkdir -p /build/apks /build/wheelhouse
# All APK signatures are checked by apk against the base image's trusted Alpine keys.
tar -xf "$INPUT/build-apks.tar" -C /build
tar -xf "$INPUT/build-cxx-apks.tar" -C /build
cp "$INPUT/patchelf-0.18.0-r3.apk" /build/apks/
apk add --no-network /build/apks/*.apk
python /build/scripts/prepare_sources.py
PIP_WHEEL=$(find /build/wheelhouse -name 'pip-*.whl' | head -n 1)
PYTHONPATH="$PIP_WHEEL" python -m pip install --no-index --no-deps --target /build/tooling /build/wheelhouse/*.whl
export PYTHONPATH=/build/tooling
export PATH=/build/tooling/bin:$PATH
export SOURCE_DATE_EPOCH=1776038400
export CFLAGS="-O2 -DNDEBUG -I/build/linux-headers/usr/include"
cmake -S "$WORK/cyclonedds" -B "$WORK/c-build"   -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_FLAGS_RELEASE="-O2 -DNDEBUG" -DENABLE_LTO=OFF -DCMAKE_INSTALL_PREFIX="$WORK/install"   -DENABLE_SSL=OFF -DENABLE_SECURITY=OFF -DBUILD_IDLC=OFF   -DBUILD_DDSPERF=OFF -DBUILD_EXAMPLES=OFF -DBUILD_TESTING=OFF
cmake --build "$WORK/c-build" --parallel 1
cmake --install "$WORK/c-build"
mkdir -p "$WORK/install/bin"
export CYCLONEDDS_HOME="$WORK/install"
export LD_LIBRARY_PATH="$WORK/install/lib"
export STANDALONE_WHEELS=1
cd "$WORK/python"
python setup.py bdist_wheel --dist-dir /build/raw-wheels
python -m auditwheel repair --plat musllinux_1_2_aarch64 --wheel-dir /build/wheels /build/raw-wheels/*.whl
python -m auditwheel show /build/wheels/*.whl
sha256sum /build/wheels/*.whl > /build/wheels/SHA256SUMS
