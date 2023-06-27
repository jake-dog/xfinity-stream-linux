# Users of pacman/nerdctl/etc may wish to change this
DOCKER_BIN ?= docker
PATCHER_IMAGE ?= widevine-relr-patcher:0.1.0

.PHONY: patcher-image patch-widevine

patch-widevine: libwidevinecdm.so.patched

patcher-image:
	@$(DOCKER_BIN) build -t $(PATCHER_IMAGE) .

libwidevinecdm.so.patched: libwidevinecdm.so
	@$(DOCKER_BIN) image inspect $(PATCHER_IMAGE) >/dev/null 2>&1 || $(MAKE) patcher-image
	@cp $< $<.new
	@$(DOCKER_BIN) run -v $(PWD):/root/patcher --rm $(PATCHER_IMAGE) ./src/patchelf --add-needed GLIBC_ABI_DT_RELR /root/patcher/$<.new
	@$(DOCKER_BIN) run -v $(PWD):/root/patcher --rm $(PATCHER_IMAGE) python3 /root/patcher/add-vernaux.py /root/patcher/$<.new /root/patcher/$@
	@$(RM) $<.new
	@$(DOCKER_BIN) image rm $(PATCHER_IMAGE)
