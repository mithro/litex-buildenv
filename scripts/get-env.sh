#! /bin/bash

SETUP_SRC=$(realpath ${BASH_SOURCE[@]})
SETUP_DIR=$(dirname $SETUP_SRC)

BINUTILS_URL=http://ftp.gnu.org/gnu/binutils/binutils-2.25.tar.gz
GCC_URL=http://mirrors-usa.go-parts.com/gcc/releases/gcc-4.9.3/gcc-4.9.3.tar.bz2
TARGET=lm32-elf

OUTPUT_DIR=$SETUP_DIR/gnu/output
mkdir -p $OUTPUT_DIR

export PATH=$OUTPUT_DIR/bin:$PATH

set -x
set -e

# Get and build gcc+binutils for the target
(
	sudo apt-get install -y build-essential

	cd gnu
	# Download binutils + gcc
	(
		mkdir -p download
		cd download
		wget -c $BINUTILS_URL
		wget -c $GCC_URL
	)

	# Build binutils for target
	sudo apt-get install -y texinfo
	(
		tar -zxvf ./download/binutils-*.tar.gz
		cd binutils-*
		mkdir -p build && cd build
		../configure --prefix=$OUTPUT_DIR --target=$TARGET
		make
		make install
	)

	# Build gcc for target
	sudo apt-get install -y libgmp-dev libmpfr-dev libmpc-dev
	(
		tar -jxvf ./download/gcc-*.tar.bz2
		cd gcc-*
		rm -rf libstdc++-v3
		mkdir -p build && cd build
		../configure --prefix=$OUTPUT_DIR --target=$TARGET --enable-languages="c,c++" --disable-libgcc --disable-libssp
		make
		make install
	)
)

# Get migen
(
	git clone https://github.com/m-labs/migen.git
	cd migen
	cd vpi
	make all
	sudo make install
)

# Get misoc
git clone https://github.com/m-labs/misoc.git

# Get libfpgalink
(
	sudo apt-get install build-essential libreadline-dev libusb-1.0-0-dev python-yaml
	wget -qO- http://tiny.cc/msbil | tar zxf -

	cd makestuff/libs
	../scripts/msget.sh makestuff/libfpgalink
	cd libfpgalink
	make deps
)

# Get the HDMI2USB-misoc-firmware
git clone https://github.com/timvideos/HDMI2USB-misoc-firmware.git

sudo apt-get install -y iverilog gtkwave