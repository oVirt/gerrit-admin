.PHONY: docs

docs:
	$(MAKE) -C docs clean
	$(MAKE) -C docs html
