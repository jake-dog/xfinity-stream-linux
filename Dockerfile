from debian:12

WORKDIR /root
RUN apt-get update && apt-get install -y git make cmake gcc g++ autoconf python3
RUN git clone https://github.com/NixOS/patchelf.git 
WORKDIR /root/patchelf
COPY ./patchelf.diff .
RUN git checkout 519766900c63f3cf227c9a38fc7aa8a53fc4f90c && git apply < ./patchelf.diff && ./bootstrap.sh && ./configure && make

CMD /bin/bash
