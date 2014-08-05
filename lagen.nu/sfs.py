# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function

import re
import os
import sys
import logging
from datetime import datetime, date

import requests
from rdflib import URIRef

from ferenda import LayeredConfig, TextReader, Describer, DocumentEntry
from ferenda import decorators, util

from ferenda.sources.legal.se import SFS as BaseSFS
from ferenda.sources.legal.se.sfs import UpphavdForfattning, IdNotFound, IckeSFS, \
    Overgangsbestammelser, Overgangsbestammelse, Register, Registerpost


class InteUppdateradSFS(Exception):
    pass


class InteExisterandeSFS(Exception):
    pass  # same as IdNotFound?


class SFS(BaseSFS):

    def __init__(self, **kwargs):
        super(SFS, self).__init__(**kwargs)
        # the new DNS-based URLs are dog slow for some reasons
        # sometimes -- a quick hack to change them back to the old
        # IP-based ones.
        for p in ('document_url_template',
                  'document_sfsr_url_template',
                  'document_sfsr_change_url_template'):
            setattr(self, p,
                    getattr(self, p).replace('rkrattsbaser.gov.se',
                                             '62.95.69.15'))
        from ferenda.manager import loglevels
        from pudb import set_trace; set_trace()
        for logname in ('paragraf', 'tabell', 'numlist', 'rubrik'):
            if 'trace' in self.config:
                if logname in self.config.trace:
                    loglevel = getattr(self.config.trace, logname)
                    if loglevel is True:
                        loglevel = logging.DEBUG
                    else:
                        loglevel = loglevels[loglevel]
                    self.trace[logname].setLevel(loglevel)
                
            else:
                # shut up logger
                self.trace[logname].propagate = False
        
    def get_default_options(self):
        opts = super(SFS, self).get_default_options()
        opts['keepexpired'] = False
        opts['revisit'] = list
        return opts
    
    def download(self, basefile=None):
        if basefile:
            ret = self.download_single(basefile)
        # following is copied from supers' download
        elif self.config.refresh or ('next_sfsnr' not in self.config):
            ret = super(SFS, self).download(basefile)
            self._set_last_sfsnr()
        else:
            ret = self.download_new()
        return ret

    def download_new(self):
        if 'next_sfsnr' not in self.config:
            self._set_last_sfsnr()
        (year, nr) = [int(
            x) for x in self.config.next_sfsnr.split(":")]
        done = False
        revisit = []
        if hasattr(self.config, 'revisit'):
            last_revisit = self.config.revisit
            for wanted_sfs_nr in last_revisit:
                self.log.info('Revisiting %s' % wanted_sfs_nr)
                try:
                    self.download_base_sfs(wanted_sfs_nr)
                except InteUppdateradSFS:
                    revisit.append(wanted_sfs_nr)

        peek = False
        last_sfsnr = self.config.next_sfsnr
        while not done:
            # first do all of last_revisit, then check the rest...
            wanted_sfs_nr = '%s:%s' % (year, nr)
            try:
                self.download_base_sfs(wanted_sfs_nr)
                last_sfsnr = wanted_sfs_nr
            except InteUppdateradSFS:
                revisit.append(wanted_sfs_nr)
            except InteExisterandeSFS:
                # try peeking at next number, or maybe next year, and
                # if none are there, we're done
                if not peek:
                    peek = True
                    self.log.info('Peeking for SFS %s:%s' % (year, nr+1)) # increments below
                elif datetime.today().year > year:
                    peek = False
                    year = datetime.today().year
                    nr = 0  # increments below, actual downloading occurs next loop
                else:
                    done = True
            nr = nr + 1

        self._set_last_sfsnr(last_sfsnr)
        self.config.revisit = revisit
        LayeredConfig.write(self.config)

    def download_base_sfs(self, wanted_sfs_nr):
        self.log.info('Looking for %s' % wanted_sfs_nr)
        (year, nr) = [int(x) for x in wanted_sfs_nr.split(":", 1)]
        base_sfsnr_list = self._check_for_sfs(year, nr)
        if base_sfsnr_list:
            # usually only a 1-elem list
            for base_sfsnr in base_sfsnr_list:
                self.download_single(base_sfsnr)
                # get hold of uppdaterad_tom from the
                # just-downloaded doc
                filename = self.store.downloaded_path(base_sfsnr)
                uppdaterad_tom = self._find_uppdaterad_tom(base_sfsnr,
                                                           filename)
                if base_sfsnr_list[0] == wanted_sfs_nr:
                    # initial grundförfattning - varken
                    # "Uppdaterad T.O.M. eller "Upphävd av" ska
                    # vara satt
                    pass
                elif util.numcmp(uppdaterad_tom, wanted_sfs_nr) < 0:
                    # the "Uppdaterad T.O.M." field is outdated --
                    # this is OK only if the act is revoked (upphavd)
                    if self._find_upphavts_genom(filename):
                        self.log.debug("    Text only updated to %s, "
                                       "but slated for revocation by %s" % 
                                       (uppdaterad_tom,
                                        self._find_upphavts_genom(filename)))
                    else:
                        self.log.warning("    Text updated to %s, not %s" %
                                         (uppdaterad_tom, wanted_sfs_nr))
                        raise InteUppdateradSFS(wanted_sfs_nr)
        else:
            raise InteExisterandeSFS(wanted_sfs_nr)
        
        
    def _check_for_sfs(self, year, nr):
        """Givet ett SFS-nummer, returnera en lista med alla
        SFS-numret för dess grundförfattningar. Normalt sett har en
        ändringsförfattning bara en grundförfattning, men för vissa
        (exv 2008:605) finns flera. Om SFS-numret inte finns alls,
        returnera en tom lista."""
        # Titta först efter grundförfattning
        self.log.debug('    Looking for base act')
        grundforf = []
        basefile = "%s:%s" % (year,nr)
        url = self.document_sfsr_url_template % {'basefile': basefile}
        t = TextReader(string=requests.get(url).text)
        try:
            t.cue("<p>Sökningen gav ingen träff!</p>")
        except IOError:  # hurra!
            grundforf.append("%s:%s" % (year, nr))
            return grundforf

        # Sen efter ändringsförfattning
        self.log.debug('    Looking for change act')
        url = self.document_sfsr_change_url_template % {'basefile': basefile}
        t = TextReader(string=requests.get(url).text)
        try:
            t.cue("<p>Sökningen gav ingen träff!</p>")
            self.log.debug('    Found no change act')
            return grundforf
        except IOError:
            t.seek(0)
            try:
                t.cuepast('<input type="hidden" name="BET" value="')
                grundforf.append(t.readto("$"))
                self.log.debug('    Found change act (to %s)' %
                               grundforf[-1])
                return grundforf
            except IOError:
                t.seek(0)
                page = t.read(sys.maxsize)
                for m in re.finditer('>(\d+:[\d\w\. ]+)</a>', page):
                    grundforf.append(m.group(1))
                    self.log.debug('    Found change act (to %s)'
                                   % grundforf[-1])
                return grundforf


    @decorators.action
    @decorators.managedparsing
    def parse(self, doc):
        # 3 ways of getting a proper doc.uri (like
        # https://lagen.nu/sfs/2008:388/konsolidering/2013:411):

        # 1. use self._find_uppdaterad_tom(sfst_file, doc.basefile). Note
        # that this value is often wrong (particularly typos are common).

        # 2. call self.parse_sfsr(sfsr_file) and find the last
        # value. Note that SFSR might be updated before SFST and so
        # the last sfs no might be later than what's really in the SFS file.

        # 3. analyse all text looking for all end-of-section markers
        # like "Lag (2013:411).", then picking the last (sane) one.

        # Ideally, we'd like to have doc.uri available early, since
        # it's input for steps 2 and 3. Therefore we go for method 1,
        # but maybe incorporate warnings (at least later on).
        sfst_file = self.store.downloaded_path(doc.basefile)

        sfsr_file = self.store.register_path(doc.basefile)
        docentry_file = self.store.documententry_path(doc.basefile)
        # workaround to fit into the RepoTester framework
        if not os.path.exists(sfsr_file):
            sfsr_file = sfst_file.replace("/downloaded/", "/register/")
        if not os.path.exists(docentry_file):
            docentry_file = sfst_file.replace(
                "/downloaded/", "/entries/").replace(".html", ".json")

        # legacy code -- try to remove this by providing doc.basefile
        # to all methods that need it
        self.id = doc.basefile

        # Check to see if this might not be a proper SFS at all
        # (from time to time, other agencies publish their stuff
        # in SFS - this seems to be handled by giving those
        # documents a SFS nummer on the form "N1992:31". Filter
        # these out.
        if doc.basefile.startswith('N'):
            raise IckeSFS("%s is not a regular SFS" % doc.basefile)

        # Check to see if the Författning has been revoked (using
        # plain fast string searching, no fancy HTML parsing and
        # traversing)
        t = TextReader(sfst_file, encoding="iso-8859-1")
        if not self.config.keepexpired:
            try:
                t.cuepast('<i>Författningen är upphävd/skall upphävas: ')
                datestr = t.readto('</i></b>')
                if datetime.strptime(datestr, '%Y-%m-%d') < datetime.today():
                    self.log.debug('%s: Expired' % doc.basefile)
                    raise UpphavdForfattning("%s is an expired SFS" % doc.basefile)
            except IOError:
                pass

        # Find out last uppdaterad_tom value
        t.seek(0)
        uppdaterad_tom = self._find_uppdaterad_tom(doc.basefile, reader=t)
        # now we can set doc.uri for reals
        doc.uri = self.canonical_uri(doc.basefile, uppdaterad_tom)
        desc = Describer(doc.meta, doc.uri)
        try:
            registry = self.parse_sfsr(sfsr_file, doc.uri)
        except (UpphavdForfattning, IdNotFound) as e:
            e.dummyfile = self.store.parsed_path(doc.basefile)
            raise e

        # for uri, graph in registry.items():
        #    print("==== %s ====" % uri)
        #    print(graph.serialize(format="turtle").decode("utf-8"))

        try:
            plaintext = self.extract_sfst(sfst_file)
            plaintextfile = self.store.path(doc.basefile, "intermediate", ".txt")
            util.writefile(plaintextfile, plaintext, encoding="iso-8859-1")
            (plaintext, patchdesc) = self.patch_if_needed(doc.basefile, plaintext)
            if patchdesc:
                desc.value(self.ns['rinfoex'].patchdescription,
                           patchdesc)

            self.parse_sfst(plaintext, doc)
        except IOError:
            self.log.warning("%s: Fulltext saknas" % self.id)
            # extractSFST misslyckades, då det fanns någon post i
            # SFST-databasen (det händer alltför ofta att bara
            # SFSR-databasen är uppdaterad).
            # attempt to find out a title from SFSR
            baseuri = self.canonical_uri(doc.basefile)
            if baseuri in registry:
                title = registry[baseuri].value(URIRef(baseuri),
                                                self.ns['dcterms'].title)
                desc.value(self.ns['dcterms'].title, title)
            desc.rel(self.ns['dcterms'].publisher,
                     self.lookup_resource("Regeringskansliet"))

            desc.value(self.ns['dcterms'].identifier, "SFS " + doc.basefile)

            doc.body = Forfattning([Stycke(['Lagtext saknas'],
                                           id='S1')])

        # At this point, we basic metadata and a almost complete body
        # structure. Enhance the metadata:
        for uri in registry.keys():
            desc.rel(self.ns['rpubl'].konsolideringsunderlag, uri)
        desc.rdftype(self.ns['rpubl'].KonsolideradGrundforfattning)
        # FIXME: make this part of head metadata
        desc.rev(self.ns['owl'].sameAs, self.canonical_uri(doc.basefile, True))
        desc.rel(self.ns['rpubl'].konsoliderar, self.canonical_uri(doc.basefile))
        desc.value(self.ns['prov'].wasGeneratedBy, self.qualified_class_name())
        de = DocumentEntry(docentry_file)
        desc.value(self.ns['rinfoex'].senastHamtad, de.orig_updated)
        desc.value(self.ns['rinfoex'].senastKontrollerad, de.orig_checked)

        # find any established abbreviation
        grf_uri = self.canonical_uri(doc.basefile)
        v = self.commondata.value(URIRef(grf_uri), self.ns['dcterms'].alternate, any=True)
        if v:
            desc.value(self.ns['dcterms'].alternate, v)

        # Finally: the dcterms:issued property for this
        # rpubl:KonsolideradGrundforfattning isn't readily
        # available. The true value is only found by parsing PDF files
        # in another docrepo. There are three general ways of finding
        # it out.
        issued = None
        # 1. if registry contains a single value (ie a
        # Grundforfattning that hasn't been amended yet), we can
        # assume that dcterms:issued == rpubl:utfardandedatum
        if len(registry) == 1 and desc.getvalues(self.ns['rpubl'].utfardandedatum):
            issued = desc.getvalue(self.ns['rpubl'].utfardandedatum)
        else:
            # 2. if the last post in registry contains a
            # rpubl:utfardandedatum, assume that this version of the
            # rpubl:KonsolideradGrundforfattning has the same dcterms:issued date
            last_post_uri = list(registry.keys())[-1]
            last_post_graph = registry[last_post_uri]
            pub_lit = last_post_graph.value(URIRef(last_post_uri),
                                            self.ns['rpubl'].utfardandedatum)
            if pub_lit:
                issued = pub_lit.toPython()
        if not issued:
            # 3. general fallback: Use the corresponding orig_updated
            # on the DocumentEntry. This is not correct (as it
            # represents the date we fetched the document, not the
            # date the document was made available), but it's as close
            # as we can get.
            issued = de.orig_updated.date()
        assert isinstance(issued, date)
        desc.value(self.ns['dcterms'].issued, issued)

        # use manual formatting of the issued date -- date.strftime
        # doesn't work with years < 1900 in older versions of python
        rinfo_sameas = "http://rinfo.lagrummet.se/publ/sfs/%s/konsolidering/%d-%02d-%02d" % (
            doc.basefile, issued.year, issued.month, issued.day)
        desc.rel(self.ns['owl'].sameAs, rinfo_sameas)

        # finally, combine data from the registry with any possible
        # overgangsbestammelser, and append them at the end of the
        # document.
        obs = {}
        obsidx = None
        for idx, p in enumerate(doc.body):
            if isinstance(p, Overgangsbestammelser):
                for ob in p:
                    assert isinstance(ob, Overgangsbestammelse)
                    obs[self.canonical_uri(ob.sfsnr)] = ob
                    obsidx = idx
                break

        if obs:
            del doc.body[obsidx]
            reg = Register(rubrik='Ändringar och övergångsbestämmelser')
        else:
            reg = Register(rubrik='Ändringar')

        for uri, graph in registry.items():
            identifier = graph.value(URIRef(uri), self.ns['dcterms'].identifier)
            identifier = identifier.replace("SFS ", "L")
            rp = Registerpost(uri=uri, meta=graph, id=identifier)
            reg.append(rp)
            if uri in obs:
                rp.append(obs[uri])

        doc.body.append(reg)
        return True

    @decorators.action
    def importarchive(self, archivefile):
        """Imports downloaded data from an archive from legacy lagen.nu data.

        In particular, creates proper archive storage for older
        versions of each text.

        """
        import tarfile
        if not tarfile.is_tarfile(archivefile):
            self.log.error("%s is not a readable tarfile" % archivefile)
            return
        t = tarfile.open(archivefile)
        current = archived = 0
        for ti in t.getmembers():
            if not ti.isfile():
                continue
            f = ti.name
            if not f.startswith("downloaded/sfst"):
                continue
            # examine f here and find out its archive version id if any
            m = re.match("downloaded/sfst/(\d+)/([\d_s\.bih]+)\.html", f) 
            if m:
                basefile = "%s:%s" % (m.group(1), m.group(2))
                version = None
                current += 1
            else:
                m = re.match("downloaded/sfst/(\d+)/([\d_s\.bih]+)-(\d+)-(\d+)\.html", f)
                if m:
                    basefile = "%s:%s" % (m.group(1), m.group(2))
                    version = "%s:%s" % (m.group(3), m.group(4))
                    archived += 1
                else:
                    m = re.match("downloaded/sfst/(\d+)/([\d_s\.bih]+)-first-version\.html", f)
                    if m:
                        basefile = "%s:%s" % (m.group(1), m.group(2))
                        version = basefile 
                        archived += 1
                    else:
                        m = re.match("downloaded/sfst/(\d+)/([\d_s\.bih]+)-(\d+)-(\d+)-checksum-(\w+)\.html", f)
                        if m:
                            basefile = "%s:%s" % (m.group(1), m.group(2))
                            version = "%s:%s\@%s" % (m.group(3), m.group(4), m.group(5))
                            # FIXME: for now, these files aren't
                            # interesting (they are not the most
                            # recent update of any particular
                            # version). but maybe might be interesting
                            # in the future?
                            continue
                        else:
                            self.log.error("Can't parse filename %s" % f)
                            continue
            basefile = basefile.replace("_", "").replace(".", "")
            # call self.store.downloaded_path to get a path
            path = self.store.downloaded_path(basefile, version)
            print("extracting %s to %s" % (f, path))
            with self.store.open_downloaded(basefile, mode="wb", version=version) as fp:
                fp.write(t.extractfile(f).read())
        self.log.info("Extracted %s current versions and %s archived versions" % (current, archived))
