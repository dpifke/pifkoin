VERSION=0.1
TGZ=dist/pifkoin-$(VERSION).tar.gz
DEB=deb_dist/python-pifkoin_$(VERSION)-1_all.deb

all: $(DEB)

install: $(DEB)
	sudo dpkg -i $(DEB)

$(TGZ): setup.py
	VERSION=$(VERSION) python setup.py sdist

$(DEB): $(TGZ)
	rm -rf deb_dist
	VERSION=$(VERSION) python setup.py --command-packages=stdeb.command bdist_deb

clean:
	rm -rf build dist deb_dist MANIFEST
	find . -type f -name '*.py[co]' -o -name '*_flymake.py' -exec rm -f '{}' ';'
	find . -type d -name '__pycache__' -exec rm -rf '{}' ';'

.PHONY: all install clean
