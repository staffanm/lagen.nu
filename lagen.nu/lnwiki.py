# -*- coding: utf-8 -*-
from __future__ import unicode_literals

# This is a set of subclasses to regular Wiki and scm.mw classes to
# customize behaviour. This should be moved out of wiki.py and into a
# separate subclass, once we have finished customizing.

# system

# 3rdparty
from lxml import etree

# mine
# from ferenda.sources.legal.se import SFS
from ferenda.sources.legal.se import SwedishLegalSource, SwedishCitationParser
from lnkeyword import LNKeyword
from sfs import SFS
from wiki import MediaWiki, WikiSemantics, WikiSettings


class LNMediaWiki(MediaWiki):
    namespaces = SwedishLegalSource.namespaces

    from ferenda.sources.legal.se.legalref import LegalRef
    
    p = LegalRef(LegalRef.LAGRUM, LegalRef.KORTLAGRUM,
                 LegalRef.FORARBETEN, LegalRef.RATTSFALL)

    keyword_class = LNKeyword

    lang = "sv"
    
    def __init__(self, config=None, **kwargs):
        super(LNMediaWiki, self).__init__(config, **kwargs)
        if self.config._parent and hasattr(self.config._parent, "sfs"):
            self.sfsrepo = SFS(self.config._parent.sfs)
        else:
            self.sfsrepo = SFS()

    def get_wikisettings(self):
        settings = LNSettings(lang=self.lang)
        # NOTE: The settings object (the make_url method) only needs
        # access to the canonical_uri method.
        settings.make_sfs_url = self.sfsrepo.canonical_uri
        settings.make_keyword_url = self.keywordrepo.canonical_uri
        return settings

    def get_wikisemantics(self, parser, settings):
        return LNSemantics(parser, settings)

    def canonical_uri(self, basefile):
        if basefile.startswith("SFS/") or basefile.startswith("SFS:"):
            # "SFS/1998:204" -> "1998:204"
            return self.sfsrepo.canonical_uri(basefile[4:])
        else:
            return super(LNMediaWiki, self).canonical_uri(basefile)
        
    def postprocess(self, doc, xhtmltree):
        # if SFS mode:
        # create a div for root content
        # find all headers, create div for everything there
        if doc.basefile.startswith("SFS/") or doc.basefile.startswith("SFS:"):
            self.postprocess_commentary(doc, xhtmltree)
            toplevel_property = False
        else:
            toplevel_property = True
        body = super(LNMediaWiki, self).postprocess(doc, xhtmltree,
                                                     toplevel_property=toplevel_property)
        citparser = SwedishCitationParser(self.p, self.config.url)
        citparser.parse_recursive(body, predicate=None)
        return body
        
    def postprocess_commentary(self, doc, xhtmltree):
        uri = doc.uri
        body = xhtmltree.getchildren()[0]
        newbody = etree.Element("body")

        curruri = uri
        currdiv = etree.SubElement(newbody, "div")
        currdiv.set("about", curruri)
        currdiv.set("property", "dcterms:description")
        currdiv.set("datatype", "rdf:XMLLiteral")
        for child in body.getchildren():
            if child.tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
                # remove that <span> element that Semantics._h_el adds for us
                assert child[0].tag == "span", "Header subelement was %s not span" % child[0].tag
                child.text = child[0].text
                child.remove(child[0])
                if child.text:
                    if isinstance(child.text, bytes):
                        txt = child.text.decode("utf-8")
                    else:
                        txt = child.text
                    nodes = self.p.parse(txt, curruri)
                    curruri = nodes[0].uri
                # body.remove(child)
                newbody.append(child) 
                currdiv = etree.SubElement(newbody, "div")
                currdiv.set("about", curruri)
                currdiv.set("property", "dcterms:description")
                currdiv.set("datatype", "rdf:XMLLiteral")
            else:
                # body.remove(child)
                currdiv.append(child)
        xhtmltree.remove(body)
        xhtmltree.append(newbody)
        

class LNSemantics(WikiSemantics):
    def internal_link(self, ast):
        el = super(LNSemantics, self).internal_link(ast)
        return el


class LNSettings(WikiSettings):
    def __init__(self, lang="en"):
        super(LNSettings, self).__init__(lang)
        from ferenda.thirdparty.mw.settings import Namespace as MWNamespace
        template_ns = MWNamespace({"prefix": "template",
                                   "ident": 10,
                                   "name": {"en": "Template",
                                            "de": "Vorlage",
                                            "sv": "Mall"}})
        self.namespaces.add(MWNamespace({"prefix": "category",
                                         "ident": 14,
                                         "name": {"en": "Category",
                                                  "de": "Kategorie",
                                                  "sv": "Kategori"}}))
        self.namespaces.add(template_ns)
        self.namespaces.add(MWNamespace({"prefix": "user",
                                         "ident": 2,
                                         "name": {"en": "User",
                                                  "de": "Benutzer",
                                                  "sv": "Användare"}}))
        self.msgcat["toc"]["sv"] = "Innehåll"
        self.templates = {("template", "TranslatedAct"):
                          "\n<small>[{{{href}}} An unofficial translation of "
                          "{{{actname}}} is available from "
                          "{{{source}}}]</small>\n"}
        
    def make_url(self, name, **kwargs):
        # uri = super(LNSettings, self).make_url(name, **kwargs)
        if name[1].startswith("SFS/"):
            uri = self.make_sfs_url(name[1][4:])
        else:
            if name[0].prefix == "user":
                uri = "https://lagen.nu/wiki/%s" % self.expand_page_name(*name)
            else:
                uri = self.make_keyword_url(name[1])
        return uri
        
