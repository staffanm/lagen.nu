# -*- coding: utf-8 -*-
from __future__ import unicode_literals

# system
from tempfile import mktemp
import random
import re
import os
from six import text_type as str

# 3rdparty
from lxml import etree

# mine
from ferenda import DocumentRepository, DocumentStore
from ferenda import util
try:
    from ferenda.thirdparty.mw import Parser, Semantics, Settings, Preprocessor
except ImportError as e:
    import sys
    if sys.version_info < (2, 7):
        raise RuntimeError("ferenda.sources.general.Wiki is not supported under python 2.6: %s" % str(e))
    else:
        raise e # dunno
        

class MediaWikiStore(DocumentStore):
    def basefile_to_pathfrag(self, basefile):
        return basefile.replace(":", os.sep).replace(" ", "_")

    def pathfrag_to_basefile(self, pathfrag):
        return pathfrag.replace("_", " ").replace(os.sep, ":")


class MediaWiki(DocumentRepository):

    """Downloads content from a Mediawiki system and converts it to annotations on other documents.

    For efficient downloads, this docrepo requires that there exists a
    XML dump (created by `dumpBackup.php
    <http://www.mediawiki.org/wiki/Manual:DumpBackup.php>`_) of the
    mediawiki contents that can be fetched over HTTP/HTTPS. Configure
    the location of this dump using the ``mediawikiexport``
    parameter::

        [mediawiki]
        class = ferenda.sources.general.MediaWiki
        mediawikiexport = http://localhost/wiki/allpages-dump.xml

    """

    alias = "mediawiki"
    downloaded_suffix = ".xml"
    documentstore_class = MediaWikiStore

    def get_default_options(self):
        opts = super(MediaWiki, self).get_default_options()
        # The API endpoint URLs change with MW language
        opts['mediawikiexport'] = 'http://localhost/wiki/Special:Export/%s(basefile)'
        opts['mediawikidump'] = 'http://localhost/wiki/allpages-dump.xml'
        opts['mediawikinamespaces'] = ['Category']
            # process pages in this namespace (as well as pages in the default namespace)
        return opts

    def download(self, basefile=None):
        if basefile:
            return self.download_single(basefile)

        if self.config.mediawikidump:
            # resp = requests.get(self.config.mediawikidump)
            # xml = etree.parse(resp.content)
            xmldumppath = self.store.path('dump', 'downloaded', '.xml')
            xml = etree.parse(xmldumppath)
        else:
            raise ConfigurationError("config.mediawikidump not set")

        MW_NS = "{%s}" % xml.getroot().nsmap[None]
        wikinamespaces = []
        # FIXME: Find out the proper value of MW_NS
        for ns_el in xml.findall("//" + MW_NS + "namespace"):
            wikinamespaces.append(ns_el.text)

        # Get list of existing basefiles - if any of those
        # does not appear in the XML dump, remove them afterwards
        basefiles = list(self.store.list_basefiles_for("parse"))

        for page_el in xml.findall(MW_NS + "page"):
            basefile = page_el.find(MW_NS + "title").text
            if basefile == "Huvudsida":
                continue
            if ":" in basefile and basefile.split(":")[0] in wikinamespaces:
                (namespace, localtitle) = basefile.split(":", 1)
                if namespace not in self.config.mediawikinamespaces:
                    continue
            p = self.store.downloaded_path(basefile)
            self.log.info("%s: extracting from XML dump" % basefile)
            with self.store.open_downloaded(basefile, "w") as fp:
                fp.write(etree.tostring(page_el, encoding="utf-8"))

            if basefile in basefiles:
                del basefiles[basefiles.index(basefile)]

        for b in basefiles:
            self.log.debug("%s: removing stale document" % b)
            util.robust_remove(self.store.downloaded_path(b))

    def download_single(self, basefile):
        # download a single term, for speed
        url = self.config.mediawikiexport % {'basefile': basefile}
        self.download_if_needed(url, basefile)

    re_anchors = re.compile('(<a.*?</a>)', re.DOTALL)
    re_anchor = re.compile('<a[^>]*>(.*)</a>', re.DOTALL)
    re_tags = re.compile('(</?[^>]*>)', re.DOTALL)

    
    def parse_document_from_soup(self, soup, doc):
        
        wikitext = soup.find("text").text
        
        parser = self.get_wikiparser()
        settings = self.get_wikisettings()
        semantics = self.get_wikisemantics(parser, settings)
        
        # a little unsure about what Preprocessor.expand actually DOES...
        wikitext = Preprocessor().expand(doc.basefile, wikitext)

        xhtml = parser.parse(wikitext, "document",
                             filename=doc.basefile,
                             semantics=semantics,
                             trace=False)

        doc.body = self.postprocess(doc, xhtml)
        return None

    def get_wikiparser(self):
        return Parser(parseinfo=False, whitespace='', nameguard=False)

    def get_wikisemantics(self, parser, settings):
        return Semantics(parser, settings)
        
    def get_wikisettings(self, parser):
        return Settings()

    def postprocess(self, doc, xhtmltree):
        # convert xhtmltree to a ferenda.Elements tree
        root = self.elements_from_node(xhtmltree)
        return root[0]

    def elements_from_node(self, node):
        
        from ferenda.elements.html import _tagmap
        assert node.tag in _tagmap
        element = _tagmap[node.tag](**node.attrib)
        if node.text:
            element.append(str(node.text))
        for child in node:
            if isinstance(child, str):
                element.append(str(child))
            else:
                subelement = self.elements_from_node(child)
                if subelement: # != None? 
                    element.append(subelement)
                if child.tail:
                    element.append(str(child.tail))
        return element

        

    # differ from the default relate_triples in that it uses a different
    # context for every basefile and clears this beforehand.
    # Note that a basefile can contain statements
    # about multiple and changing subjects, so it's not trivial to erase all
    # statements that stem from a basefile w/o a dedicated context.
    def relate_triples(self, basefile):
        context = self.dataset_uri + "#" + basefile.replace(" ", "_")
        ts = self._get_triplestore()
        data = open(self.store.distilled_path(basefile)).read()
        ts.clear(context=context)
        ts.add_serialized(data, format="xml", context=context)

class SFSMediaWiki(MediaWiki):
    re_sfs_uri = re.compile('https?://[^/]*lagen.nu/(\d+):(.*)')
    re_dom_uri = re.compile('https?://[^/]*lagen.nu/dom/(.*)')

    from ferenda.sources.legal.se.legalref import LegalRef
    
    p = LegalRef(LegalRef.LAGRUM, LegalRef.KORTLAGRUM,
                 LegalRef.FORARBETEN, LegalRef.RATTSFALL)


    def get_wikisettings(self):
        return SFSSettings()

    def get_wikisemantics(self, parser, settings):
        return SFSSemantics(parser, settings)

    def canonical_uri(self, basefile):
        return "%sres/%s/%s" % (self.config.url,
                                self.alias,
                                basefile.replace(" ", "_"))
        

    def postprocess(self, doc, xhtmltree):
#        # find out the URI that this wikitext describes
#        if doc.basefile.startswith("SFS/"):
#            sfs_basefile = basefile.split("/", 1)[1]
#            # FIXME: our parse() needs access to a correctly
#            # configured SFS object (with it's self.config.url +
#            # self.config.urlpath). We could dig around in like
#            # self.config._parent.sfs for settings and instantiate it
#            # ourselves, but...
#            uri = "https://lagen.nu/%s" % sfs_basefile
#            rdftype = None
#        else:
#            # FIXME: we should try to get hold of a configured
#            # ferenda.sources.general.keywords object (or any subclass
#            # thereof...)
#            uri = "http://lagen.nu/begrepp/" + doc.basefile.replace(" ", "_")
#            rdftype = self.ns['skos'].Concept
#
#        if rdftype:
#            body.set("typeof", "skos:Concept")
#            heading = etree.SubElement(body, "h")
#            heading.set("property", "rdfs:label")
#            heading.text = doc.basefile
#
#        main = etree.SubElement(body, "div")
#        main.set("property", "dcterms:description")
#        main.set("datatype", "rdf:XMLLiteral")
#        current = main
#        currenturi = uri
#
#        for child in xhtmltree:
#            if not rdftype and child.tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
#                nodes = p.parse(child.text, uri)
#                try:
#                    suburi = nodes[0].uri
#                    currenturi = suburi
#                    self.log.debug("    Sub-URI: %s" % suburi)
#                    h = etree.SubElement(body, child.tag)
#                    h.text = child.text
#                    current = etree.SubElement(body, "div")
#                    current.set("about", suburi)
#                    current.set("property", "dcterms:description")
#                    current.set("datatype", "rdf:XMLLiteral")
#                except AttributeError:
#                    self.log.warning(
#                        '%s är uppmärkt som en rubrik, men verkar inte vara en lagrumshänvisning' % child.text)
#            else:
#                serialized = etree.tostring(child, 'utf-8').decode('utf-8')
#                separator = ""
#                while separator in serialized:
#                    separator = "".join(
#                        random.sample("ABCDEFGHIJKLMNOPQRSTUVXYZ", 6))
#
#                markers = {}
#                res = ""
#                # replace all whole <a> elements with markers, then
#                # replace all other tags with markers
#                for (regex, start) in ((self.re_anchors, '<a'),
#                                      (self.re_tags, '<')):
#                    for match in re.split(regex, serialized):
#                        if match.startswith(start):
#                            marker = "{%s-%d}" % (separator, len(markers))
#                            markers[marker] = match
#                            res += marker
#                        else:
#                            res += match
#                    serialized = res
#                    res = ""
#
#                # Use LegalRef to parse references, then rebuild a
#                # unicode string.
#                parts = p.parse(serialized, currenturi)
#                for part in parts:
#                    if isinstance(part, Link):
#                        res += '<a class="lr" href="%s">%s</a>' % (
#                            part.uri, part)
#                    else:  # just a text fragment
#                        res += part
#
#                # restore the replaced markers
#                for marker, replacement in list(markers.items()):
#                    # print "%s: '%s'" % (marker,util.normalize_space(replacement))
#                    # normalize URIs, and remove 'empty' links
#                    if 'href="https://lagen.nu/"' in replacement:
#                        replacement = self.re_anchor.sub('\\1', replacement)
#                    elif self.re_sfs_uri.search(replacement):
#                        replacement = self.re_sfs_uri.sub(
#                            'http://rinfo.lagrummet.se/publ/sfs/\\1:\\2', replacement)
#                    elif self.re_dom_uri.search(replacement):
#                        replacement = self.re_dom_uri.sub(
#                            'http://rinfo.lagrummet.se/publ/rattsfall/\\1', replacement)
#                    # print "%s: '%s'" % (marker,util.normalize_space(replacement))
#                    res = res.replace(marker, replacement)
#
#                current.append(etree.fromstring(res.encode('utf-8')))

        return super(SFSMediaWiki, self).postprocess(doc, xhtmltree)


class SFSSemantics(Semantics):
    def internal_link(self, ast):
        el = super(SFSSemantics, self).internal_link(ast)
        return el

        
class SFSSettings(Settings):
    def make_url(self, name, **kwargs):
        uri = super(SFSSettings, self).make_url(name, **kwargs)
        return uri
        

# class LinkedWikimarkup(wikimarkup.Parser):
class LinkedWikimarkup(object):
    def __init__(self, show_toc=True):
        super(wikimarkup.Parser, self).__init__()
        self.show_toc = show_toc

    def parse(self, text):
        # print "Running subclassed parser!"
        utf8 = isinstance(text, str)
        text = wikimarkup.to_unicode(text)
        if text[-1:] != '\n':
            text = text + '\n'
            taggedNewline = True
        else:
            taggedNewline = False

        text = self.strip(text)
        text = self.removeHtmlTags(text)
        text = self.doTableStuff(text)
        text = self.parseHorizontalRule(text)
        text = self.checkTOC(text)
        text = self.parseHeaders(text)
        text = self.parseAllQuotes(text)
        text = self.replaceExternalLinks(text)
        if not self.show_toc and text.find("<!--MWTOC-->") == -1:
            self.show_toc = False
        text = self.formatHeadings(text, True)
        text = self.unstrip(text)
        text = self.fixtags(text)
        text = self.replaceRedirect(text)
        text = self.doBlockLevels(text, True)
        text = self.unstripNoWiki(text)
        text = self.replaceImageLinks(text)
        text = self.replaceCategories(text)
        text = self.replaceAuthorLinks(text)
        text = self.replaceWikiLinks(text)
        text = self.removeTemplates(text)

        text = text.split('\n')
        text = '\n'.join(text)
        if taggedNewline and text[-1:] == '\n':
            text = text[:-1]
        if utf8:
            return text.encode("utf-8")
        return text

    re_labeled_wiki_link = re.compile(r'\[\[([^\]]*?)\|(.*?)\]\](\w*)')
                                      # is the trailing group really needed?
    re_wiki_link = re.compile(r'\[\[([^\]]*?)\]\](\w*)')
    re_img_uri = re.compile('(https?://[\S]+\.(png|jpg|gif))')
    re_template = re.compile(r'{{[^}]*}}')
    re_category_wiki_link = re.compile(r'\[\[Kategori:([^\]]*?)\]\]')
    re_inline_category_wiki_link = re.compile(
        r'\[\[:Kategori:([^\]]*?)\|(.*?)\]\]')
    re_image_wiki_link = re.compile(r'\[\[Fil:([^\]]*?)\s*\]\]')
    re_author_wiki_link = re.compile(r'\[\[(Användare:[^\]]+?)\|(.*?)\]\]')

    def capitalizedLink(self, m):
        if m.group(1).startswith('SFS/'):
            uri = 'http://rinfo.lagrummet.se/publ/%s' % m.group(1).lower()
        else:
            uri = 'http://lagen.nu/concept/%s' % util.ucfirst(
                m.group(1)).replace(' ', '_')

        if len(m.groups()) == 3:
            # lwl = "Labeled WikiLink"
            return '<a class="lwl" href="%s">%s%s</a>' % (uri, m.group(2), m.group(3))
        else:
            return '<a class="wl" href="%s">%s%s</a>' % (uri, m.group(1), m.group(2))

    def categoryLink(self, m):
        uri = 'http://lagen.nu/concept/%s' % util.ucfirst(
            m.group(1)).replace(' ', '_')

        if len(m.groups()) == 2:
            # lcwl = "Labeled Category WikiLink"
            return '<a class="lcwl" href="%s">%s</a>' % (uri, m.group(2))
        else:
            # cwl = "Category wikilink"
            return '<a class="cwl" href="%s">%s</a>' % (uri, m.group(1))

    def hiddenLink(self, m):
        uri = 'http://lagen.nu/concept/%s' % util.ucfirst(
            m.group(1)).replace(' ', '_')
        return '<a class="hcwl" rel="dcterms:subject" href="%s"/>' % uri

    def imageLink(self, m):
        uri = 'http://wiki.lagen.nu/images/%s' % m.group(1).strip()
        return '<img class="iwl" src="%s" />' % uri

    def authorLink(self, m):
        uri = 'http://wiki.lagen.nu/index.php/%s' % util.ucfirst(
            m.group(1)).replace(' ', '_')
        return '<a class="awl" href="%s">%s</a>' % (uri, m.group(2))

    def replaceWikiLinks(self, text):
        # print "replacing wiki links: %s" % text[:30]
        text = self.re_labeled_wiki_link.sub(self.capitalizedLink, text)
        text = self.re_wiki_link.sub(self.capitalizedLink, text)
        return text

    def replaceImageLinks(self, text):
        # emulates the parser when using$ wgAllowExternalImages
        text = self.re_img_uri.sub('<img src="\\1"/>', text)
        # handle links like [[Fil:SOU_2003_99_s117.png]]
        text = self.re_image_wiki_link.sub(self.imageLink, text)
        return text

    def replaceAuthorLinks(self, text):
        # links to author descriptions should point directly to the wiki
        return self.re_author_wiki_link.sub(self.authorLink, text)

    def removeTemplates(self, text):
        # removes all usage of templates ("{{DISPLAYTITLE:Avtalslagen}}" etc)
        return self.re_template.sub('', text)

    def replaceCategories(self, text):
        # inline links ("Inom [[:Kategori:Allmän avtalsrätt|Allmän avtalsrätt]] studerar man...")
        text = self.re_inline_category_wiki_link.sub(self.categoryLink, text)
        # Normal category links - replace these with hidden RDFa typed links
        text = self.re_category_wiki_link.sub(self.hiddenLink, text)
        return text

    re_redirect = re.compile("^#REDIRECT ")

    def replaceRedirect(self, text):
        return self.re_redirect.sub("Se ", text)
