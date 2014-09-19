# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from ferenda.testutil import RepoTester, parametrize_repotester
from ferenda.testutil import Py23DocChecker
import doctest
import unittest
from datetime import date

# SUT
import dv
from ferenda import fsmparser


class TestDV(RepoTester):
    repoclass = dv.DV
    docroot = "../../ferenda/test/files/repo/dv"
parametrize_repotester(TestDV)


class TestDVParserBase(unittest.TestCase):
    maxDiff = None
    method = "none"
    def t(self, want, testdata, basefile="HDO/T1-14"):
        p = dv.DV.get_parser(basefile)
        p.reader = fsmparser.Peekable([testdata])
        p._state_stack = ["notbody"] # to avoid the special fallback rule in is_instans
        for f in p.recognizers:
            if f.__name__ == self.method:
                break
        else:
            self.fail("Could not find a recognizer function named %s" % self.method)
        self.assertEqual(want, f(p))
    


class TestInstans(TestDVParserBase):
    method = "is_instans"
    # SHOULD work
    def test_plain_courtname(self):
        self.t({'court': 'Örebro tingsrätt', 'complete': True},
               'Örebro tingsrätt')
        self.t({'court': 'Hovrätten över Skåne och Blekinge', 'complete': True},
               'Hovrätten över Skåne och Blekinge')
        self.t({'court': 'Högsta domstolen', 'complete': True},
               'Högsta domstolen')

    # SHOULD work
    def test_not_courtname(self):
        self.t({},
               'Jönköpings tingsrätt beslutade att...')

    # SHOULD work
    def test_tr_aklagare(self):
        self.t({'court': 'Malmö TR'},
               'Allmän åklagare yrkade vid Malmö TR ansvar å S.S')
        self.t({'court': 'Södra Roslags TR'},
               'Allmän åklagare yrkade vid Södra Roslags TR ansvar på T.O.')
        self.t({'court': 'Sollefteå TR'},
               'Allmän åklagare yrkade efter ansökan om stämning å E.T. vid '
               'Sollefteå TR, att')
        self.t({'court': 'Stockholms TR'},
               'Allmän åklagare yrkade efter stämning å handelsbolaget och '
               'B.F. vid Stockholms TR, att')

    # SHOULD work
    def test_tr_karande(self):
        self.t({'court': 'Södra Roslags TR'},
               'Efter ansökan om stämning å H.N. vid Södra Roslags TR yrkade '
               'bolaget förpliktande för H.N. att till bolaget utge')
        self.t({'court': 'Motala TR'},
               'Mjölby - Svartådalen Energiverk AB (bolaget) förde efter '
               'stämning å lantbrukaren i H.T. vid Motala TR den talan som '
               'framgår')
        self.t({'court': 'Stockholms TR'},
               'Lillebil yrkade efter stämning å Stockholms läns landsting '
               'vid Stockholms TR att landstinget skulle')

    # SHOULD work
    def test_tr_ansokan(self):
        self.t({'court': 'Helsingborgs TR'},
               'Makarna H.A., född d 15 maj 1955, och M.E., född d 21 sept '
               '1967, ansökte vid Helsingborgs TR om tillstånd att såsom '
               'adoptivbarn')
        self.t({'court': 'Stockholms TR'},
               'I.C., född 1968, ansökte vid Stockholms TR om stämning å '
               'KFA med yrkande att KFA måtte åläggas att')
        
    # SHOULD work
    def test_hovr_aklagare(self):
        self.t({'court': 'Svea HovR'},
               'Riksåklagaren väckte i Svea HovR åtal mot rådmannen Carin A. '
               'för tjänstefel enligt ')

    # SHOULD work
    def test_hovr(self):
        self.t({'court': 'Svea HovR'},
               'B.A. fullföljde talan i Svea HovR och yrkade i första '
               'hand att')
        self.t({'court': 'Göta HovR'},
               'Bolaget fullföljde talan i Göta HovR och yrkade bifall till '
               'sin vid TR:n förda talan. ')
        self.t({'court': 'HovR:n för Västra Sverige'},
               'Broschyrbolaget fullföljde talan i HovR:n för Västra Sverige '
               'och yrkade att')
        self.t({'court': 'Svea HovR'},
               'Lillebil överklagade i Svea HovR och yrkade att HovR:n skulle '
               'fastställa att')
        self.t({'court': 'HovR:n för Nedre Norrland'},
               'M.B. överklagade TR:ns dom endast i skadeståndsdelen i HovR:n '
               'för Nedre Norrland, som d. 23 juni 1998 förelade ')

    # SHOULD work
    def test_hd(self):
        self.t({'court': True},  # True?
               'B.A. sökte revision och yrkade, att gärningen måtte bedömas')
        self.t({'court': 'HD'},
               'H.T. (ombud advokaten O.R.) sökte revision och yrkade att HD '
               'måtte fastställa TR:ns dom i huvudsaken')
        self.t({'court': True},  # True?
               'Såväl Broschyrbolaget (ombud advokaten G.R.) som Sperlingsholm'
               ' sökte revision. ')
        self.t({'court': True},  # True?
               'H.A. och M.E. (ombud för båda advokaten G.N.) anförde besvär '
               'och yrkade bifall till adoptionsansökningen.')
        self.t({'court': True},  # True?
               'Lillebil (ombud advokaten M.L.) överklagade och yrkade bifall '
               'till sin talan i HovR:n. ')
        self.t({'court': 'HD'},
               'T.L. överklagade för egen del och yrkade att HD skulle besluta'
               ' att ersättning')
        self.t({'court': 'HD'},
               'Carin A. (offentlig försvarare advokaten P.A.) överklagade och'
               ' yrkade i själva saken att HD skulle befria henne från ansvar')

    # SHOULD work
    def test_hd_ansokan(self):
        self.t({'court': 'HD'},
               'S.W. anhöll i ansökan som inkom till HD d 14 okt 1980 om '
               'återställande av försutten tid')

    # SHOULD work
    def test_hd_skrivelse(self):
        self.t({'court': 'HD'},
               'Kalmar tingsrätt anförde i en till HD den 1 november 2010 '
               'ställd skrivelse i huvudsak följande')

    # SHOULD work 
    def test_hd_aklagare(self):
        self.t({'court': 'HD'},
               'Riksåklagaren väckte i HD åtal mot J.S, M.L och A.C för '
               'tjänstefel med följande gärningsbeskrivning')

    # SHOULD work 
    def test_forvaltningsmynd(self):
        self.t({'court': 'Skatteverket'},
               'AB Cerbo (bolaget) yrkade i skattedeklaration för december '
               '2006 avdrag med 193 180 kr avseende ingående mervärdesskatt '
               'vid förvärv av konsulttjänster från Finland. Tjänsterna avsåg '
               'biträde vid avyttring av ett finskt dotterbolag. Skatteverket '
               'vägrade i beslut den 14 februari 2007 avdraget med följande '
               'motivering:',
               basefile="HFD/1")
        self.t({'court': 'Omsorgsnämnden i Trollhättans kommun'},
               'Omsorgsnämnden i Trollhättans kommun bedömde i biståndsbeslut '
               'i oktober 2003 respektive december 2003 att',
               basefile="HFD/1")
        self.t({'court': 'Försäkringskassan',
                'date': date(2010, 8, 17)},
               'S.G.P. fick genom dom av Högsta förvaltningsdomstolen den 20 '
               'juli 2010 rätt till halv sjukersättning för perioden augusti '
               '2006 - juni 2008. Försäkringskassan beslutade därefter den 17 '
               'augusti 2010 att S.G.P. inte hade rätt till någon '
               'utbetalning med anledning av domen.',
               basefile="HFD/1")
        self.t({'court': 'Skatterättsnämnden'},
               'I ansökan hos Skatterättsnämnden om förhandsbesked anförde X '
               'bl.a. följande. ',
               basefile="HFD/1")
        self.t({'court': 'Skattemyndigheten'},
               'Skattemyndigheten beslutade i två skilda beslut att påföra '
               'Bostadsaktiebolaget Poseidon ',
               basefile="HFD/1")
        self.t({'court': 'Skatterättsnämnden'},
               'I en ansökan hos Skatterättsnämnden om förhandsbesked '
               'anförde Advokat X AB och Advokat Y AB',
               basefile="HFD/1")

    # SHOULD work
    def test_fr(self):
        self.t({'court': True},
               'Bolaget överklagade och yrkade att påförd avkastningsskatt '
               'skulle ...')
        self.t({'court': 'länsrätten'},
               'Makarna överklagade omsorgsnämndens beslut hos länsrätten och '
               'anförde bl.a. följande.')
        self.t({'court': 'länsrätten'},
               'Bolaget överklagade Skatteverkets beslut hos länsrätten och '
               'yrkade')

    # SHOULD work
    def test_kamr(self):
        self.t({'court': 'kammarrätten'},
               'Bolaget överklagade och yrkade att kammarrätten skulle ändra '
               'länsrättens domar och undanröja')
        self.t({'court': 'kammarrätten'},
               'A-B.C. och A.C. överklagade och yrkade att kammarrätten, med '
               'ändring av länsrättens domar, skulle')
        self.t({'court': 'kammarrätten'},
               'Skatteverket överklagade länsrättens dom hos kammarrätten och '
               'yrkade i första hand ')

    # SHOULD work
    def test_hfd(self):
        self.t({'court': 'Regeringsrätten'},
               'I besvär hos Regeringsrätten yrkade X att förhandsbeskedet '
               'skulle ändras på så sätt att',
               basefile="HFD/1")
        self.t({'court': True},
               'Bolaget fullföljde sin talan.',
               basefile="HFD/1")
        self.t({'court': 'Regeringsrätten'},
               'Bolagen samt X och Y överklagade och yrkade att '
               'Regeringsrätten, med ändring av Skatterättsnämndens beslut, '
               'skulle',
               basefile="HFD/1")
        self.t({'court': True},
               'A-B.C. och dödsboet efter A.C. överklagade kammarrättens '
               'domar och anförde bl.a. följande. ',
               basefile="HFD/1")
        self.t({'court': True},
               'Skatteverket överklagade kammarrättens dom och yrkade att '
               'bolaget inte',
               basefile="HFD/1")

    def test_miv(self):
        self.t({'court': 'Migrationsverket', 'date': date(2006,2,14)},
               'Migrationsverket beslutade den 14 februari 2006 att avslå '
               'M A B A:s ansökan om uppehållstillstånd m.m. samt att avvisa '
               'honom',
               basefile="MIG/1")
        self.t({'court': 'Migrationsverket', 'date': date(2012, 8, 6)},
                'I sitt beslut den 6 augusti 2012 avslog Migrationsverket '
                'bl.a. A:s ansökan om uppehållstillstånd och avvisade honom '
                'från Sverige',
               basefile="MIG/1")

    def test_migr(self):
        self.t({'court': True},
               'M A B A överklagade beslutet. Migrationsverket bestred... ',
               basefile="MIG/1")
        self.t({'court': 'Länsrätten i Skåne län, migrationsdomstolen'},
               'A överklagade Migrationsverkets beslut i ersättningsfrågan '
               'till Länsrätten i Skåne län, migrationsdomstolen, som i dom '
               'den 21 oktober 2009 (ordförande Geijer) tillerkände A '
               'ersättning',
               basefile="MIG/1")

    def test_miod(self):
        self.t({'court': 'Migrationsöverdomstolen'},
               'M A B A överklagade domen till Migrationsöverdomstolen. '
               'Migrationsverket bestred bifall till överklagandet.',
               basefile="MIG/1")
        self.t({'court': 'Migrationsöverdomstolen'},
               'Migrationsverket överklagade domen till '
               'Migrationsöverdomstolen och yrkade att ',
               basefile="MIG/1")
        

class TestDom(TestDVParserBase):
    method = "is_dom"

    # SHOULD work
    def test_fr_yttrande(self):
        self.t({'court': 'Förvaltningsrätten i Göteborg',
                'date': date(2011, 4, 21)},
               'Förvaltningsrätten i Göteborg (2011-04-21, ordförande '
               'Hasselberg) yttrade: Tillämplig bestämmelse',
               basefile="HFD/1")
        self.t({'court': 'Kammarrätten i Göteborg',
                'date': date(2011, 11, 2)},
               'Kammarrätten i Göteborg (2011-11-02, Nyström, Nilsson, '
               'referent, Sjögren Samuelsson) yttrade: Frågan i målet är...',
               basefile="HFD/1")
        self.t({'court': 'Högsta förvaltningsdomstolen',
                'date': date(2013, 5, 27)},
               'Högsta förvaltningsdomstolen (2013-05-27, Jermsten, Dexe, '
               'Silfverberg, Bull) yttrade:',
               basefile="HFD/1")

    def test_everything(self):
        self.t({'court': 'TR', 'date': date(1980, 9, 15)},
               'TR:n (ordf t f lagmannen Garenborg) anförde i dom d 15 sept '
               '1980:')
        self.t({'court': 'HovR', 'date': date(1980, 11, 7)},
               'HovR:n (hovrättsrådet Wedin, referent, adjungerade ledamoten '
               'Melchior samt nämndemännen Forslund och Arnåker) anförde i '
               'dom d 7 nov 1980:')
        self.t({'court': 'HD'},
               'Målet avgjordes efter huvudförhandling av HD (JustR:n Hult, '
               'Welamson, referent, Erik Nyman, Ehrner och Rydin), som beslöt '
               'följande dom: ')
        self.t({'court': 'TR', 'date': date(1977, 4, 28)},
               'TR:n (tingsdomaren Olsén, hovrättsrådet E Larsson och '
               'tingsfiskalen Svanberg) anförde i dom d 28 april 1977: : '
               'Till utvecklande av sin talan')
        self.t({'court': 'HovR', 'date': date(1978, 6, 16)},
               'HovR:n (presidenten Rudholm, hovrättsråden Loheman, referent, '
               'och Grönvall samt adj led Malmqvist) fastställde i dom d 16 '
               'juni 1978 TR:ns dom. ')
        self.t({'court': 'HD'},
               'Målet avgjordes efter huvudförhandling i HD (JustR:n Hult, '
               'Westerlind, Höglund, Sven Nyman och Jermsten, referent) som '
               'beslöt följande dom: ')
        self.t({'court': 'HD'},
               'HD (JustR:n Hult, Westerlind, Brundin, Hessler och Rydin, '
               'referent) fattade slutligt beslut i enlighet med betänkandet.')
        self.t({'court': 'TR', 'date': date(1988, 10, 17)},
               "TR:n (lagmannen Matz, rådmannen Fogelberg och tingsfiskalen "
               "von Schéele) anförde i dom d 17 okt 1988: ")
        self.t({'court': 'HovR', 'date': date(1989, 6, 16)},
               "HovR:n (hovrättsråden Rehnberg och Mogren, referent samt adj "
               "led Landerholm) anförde i dom d 16 juni 1989: ")
        self.t({'court': 'HD'},
               "HD (JustR:n Vängby, Lars Å Beckman, Törnell och Danelius, "
               "referent) beslöt följande dom:")
        self.t({'court': 'TR', 'date': date(1988, 10, 31)},
               "TR:n (lagmannen Ljunggren, t f rådmannen Krantz och tings"
               "fiskalen Erdmann) anförde i dom d 31 okt 1988: Yrkanden m m")
        # This one is difficult -- OCR or transcribing has missed the
        # starting left paranthesis.
        # self.t({'court': 'HovR', 'date': date(1989, 6, 13)},
        #       "HovR:n fd hovrättsrådet Jagander och tf hovrättsassessorn "
        #       "Månsson, referent) anförde i dom d 13 juni 1989:")
        self.t({'court': 'HD'},
               "HD (JustR:n Vängby, Lars Å Beckman, Törnell och Danelius, "
               "referent) beslöt följande dom: ")
        self.t({'court': 'TR', 'date': date(1989, 3, 20)},
               "TR:n (rådmannen Nilsson) anförde i beslut d 20 mars 1989: "
               "M.E. är född d 21 sept 1967")
        self.t({'court': 'HovR', 'date': date(1989, 6, 2)},
               "HovR:n (hovrättslagmannen Aspelin, hovrättsrådet Nilsson, "
               "referent, och adj led Ralf Larsson) anförde i beslut d "
               "2 juni 1989: ")
        self.t({'court': 'HD'},
               "HD (JustR:n Jermsten, Gregow, Solerud, Lars Å Beckman och "
               "Törnell, referent) fattade slutligt beslut i enlighet med "
               "betänkandet.")
        self.t({'court': 'TR', 'date': date(1989, 11, 16)},
               "TR:n (tre nämndemän) anförde i dom d 16 nov 1989 bl a: ")
        self.t({'court': '', 'date': date(2014,9,18)},
               "HovR:n (hovrättslagmannen Edling, referent, samt nämndemännen Larsson och Carlsson) anförde i dom d 27 mars 1990: ")
        self.t({'court': '', 'date': date(2014,9,18)},
               "HD (JustR:n Jermsten, Gregjow, Svensson, Munck och Danelius, referent) beslöt följande dom: ")
        self.t({'court': '', 'date': date(2014,9,18)},
               "TR:n (rådmannen Nöteberg) anförde i dom d. 8 dec. 1997: Domskäl. Landstinget har i öppen upphandling enligt LOU ")
        self.t({'court': '', 'date': date(2014,9,18)},
               "HovR:n (tf. hovrättsassessorn Magnus Eriksson, referent) anförde i dom d. 22 dec. 1998: Domskäl. Utredningen här är i allt ")
        self.t({'court': '', 'date': date(2014,9,18)},
               "HD (JustR:n Magnusson, Nyström, Munck, Blomstrand och Lundius, referent) beslöt följande dom: Domskäl. Sedan Danderyds sjukhus infordrat anbud på vissa biltransporter")
        self.t({'court': '', 'date': date(2014,9,18)},
               "HovR:n (hovrättslagmannen Laven samt hovrättsråden Similä, referent, och Lind) stadfäste i dom d. 3 juli 1998 den mellan M.B. och A.L. såsom målsägande...")
        self.t({'court': '', 'date': date(2014,9,18)},
               "HD (JustR:n Nyström, Danelius, Blomstrand, Håstad, referent, och Lundius) fattade följande slutliga beslut: Skäl. T.L. har som grund")
        self.t({'court': '', 'date': date(2014,9,18)},
               "HovR:n (hovrättslagmannen Eklycke samt hovrättsråden Hesser, referent, och Thuresson) anförde i dom d. 5 nov. 1998: Yrkanden m. m")
        self.t({'court': '', 'date': date(2014,9,18)},
               "HD (JustR:n Magnusson, Lennander, referent, och Pripp) beslöt följande dom: Domskäl. Carin A. har i HD intagit samma")
        self.t({'court': '', 'date': date(2014,9,18)},
               "Tingsrätten (ordförande f.d. lagmannen Sture Stenström) meddelade dom den 22 januari 2009.")
        self.t({'court': '', 'date': date(2014,9,18)},
               "Hovrätten (hovrättslagmannen Jan Carrick , hovrättsrådet Johan Stenberg och två nämndemän) anförde i dom den 18 mars 2009: ")
        self.t({'court': '', 'date': date(2014,9,18)},
               "HD (justitieråden Per Virdesten, Lena Moore, Göran Lambertz och Johnny Herre, referent) meddelade den 3 januari 2011 följande dom:")
        self.t({'court': '', 'date': date(2014,9,18)},
               "HD (justitieråden Dag Victor, Stefan Lindskog, referent, Göran Lambertz, Johnny Herre och Ingemar Persson) meddelade den 15 februari 2011 följande beslut: ")
        self.t({'court': '', 'date': date(2014,9,18)},
               "Tingsrätten (ordförande rådmannen Sven Cavallin) anförde i dom den 15 september 2009 bl.a.: ")
        self.t({'court': '', 'date': date(2014,9,18)},
               "Hovrätten (hovrättsråden Marianne Lejman och Torbjörn Nordenson, tf. hovrättsassessorn Martin Sunnqvist och två nämndemän) anförde i dom den 9 mars 2010")
        self.t({'court': '', 'date': date(2014,9,18)},
               "HD (justitieråden Dag Victor, Stefan Lindskog, Lena Moore, referent, Göran Lambertz och Johnny Herre) meddelade den 30 mars 2011 följande dom:")
        self.t({'court': '', 'date': date(2014,9,18)},
               "SAKEN")
        self.t({'court': '', 'date': date(2014,9,18)},
               "Kammarrätten i Stockholm, Migrationsöverdomstolen (2010-02-23, Schött, Råberg, referent och Brege Gefvert), yttrade: ")
        self.t({'court': '', 'date': date(2014,9,18)},
               "I sin dom avslog Förvaltningsrätten i Stockholm, migrationsdomstolen (2013- 03-25, ordförande van der Stad och tre nämndemän), A:s överklagande. Domstolen")
        self.t({'court': '', 'date': date(2014,9,18)},
               "Kammarrätten i Stockholm, Migrationsöverdomstolen (2014-02-11, Jagander, Renman, referent, och Axelsson), yttrade: ")
