# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from keywords import Keyword


class LNKeyword(Keyword):
    lang = "sv"
    def __init__(self, config=None, **kwargs):
        super(Keyword, self).__init__(config, **kwargs)
        self.termset_funcs = []

    def canonical_uri(self, basefile):
        # FIXME: make configurable like SFS.canonical_uri
        return "https://lagen.nu/concept/%s" % basefile.replace(" ", "_")

    def basefile_from_uri(self, uri):
        prefix = "https://lagen.nu/concept/"
        if prefix in uri:
            return uri.replace(prefix, "").replace("_", " ")
        else:
            return super(LNKeyword, self).basefile_from_uri(uri)
        
