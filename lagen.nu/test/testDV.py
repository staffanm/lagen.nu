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


class TestDVUnit(unittest.TestCase):

    def t(self, want, testdata):
        p = dv.DV.get_parser()
        p.reader = fsmparser.Peekable([testdata])
        p._state_stack = ["notbody"] # to avoid the special fallback rule in is_instans
        f = p.recognizers[2]
        assert f.__name__ == "is_instans", "The order of recognizers seem to have shifted, expected 'is_instans', got %s" % f.__name__
        self.assertEqual(want, f(p))

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
    def test_fr_yttrade(self):
        self.t({'court': 'Förvaltningsrätten i Göteborg',
                'date': date(2011, 4, 21),
                'constitution': [{'name': 'Hasselberg',
                                  'position': 'ordförande'}]},
               'Förvaltningsrätten i Göteborg (2011-04-21, ordförande '
               'Hasselberg) yttrade: Tillämplig bestämmelse')
        self.t({'court': 'Kammarrätten i Göteborg',
                'date': date(2011, 11, 2),
                'constitution': [{'name': 'Nyström'},
                                 {'name': 'Nilsson', 'position': 'referent'},
                                 {'name': 'Sjögren Samuelsson'}]},
               'Kammarrätten i Göteborg (2011-11-02, Nyström, Nilsson, '
               'referent, Sjögren Samuelsson) yttrade: Frågan i målet är...')
        self.t({'court': 'Högsta förvaltningsdomstolen',
                'date': date(2013, 5, 27),
                'constitution': [{'name': 'Jermsten'},
                                 {'name': 'Dexe'},
                                 {'name': 'Silfverberg'},
                                 {'name': 'Bull'}]},
               'Högsta förvaltningsdomstolen (2013-05-27, Jermsten, Dexe, '
               'Silfverberg, Bull) yttrade:')

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
        self.t({'court': True, 'prevcourt': 'HovR:n'},  # True?
               'Lillebil (ombud advokaten M.L.) överklagade och yrkade bifall '
               'till sin talan i HovR:n. ')
        self.t({'court': 'HD'},
               'T.L. överklagade för egen del och yrkade att HD skulle besluta'
               ' att ersättning')
        self.t({'court': 'HD'},
               'Carin A. (offentlig försvarare advokaten P.A.) överklagade och'
               ' yrkade i själva saken att HD skulle befria henne från ansvar')

    def test_hd_ansokan(self):
        self.t({'court': 'HD'},
               'S.W. anhöll i ansökan som inkom till HD d 14 okt 1980 om '
               'återställande av försutten tid')

    def test_hd_skrivelse(self):
        self.t({'court': 'HD'},
               'Kalmar tingsrätt anförde i en till HD den 1 november 2010 '
               'ställd skrivelse i huvudsak följande')

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
               'motivering:')
        self.t({'court': 'Omsorgsnämnden i Trollhättans kommun'},
               'Omsorgsnämnden i Trollhättans kommun bedömde i biståndsbeslut '
               'i oktober 2003 respektive december 2003 att')
        self.t({'court': 'Försäkringskassan',
                'date': date(2010, 8, 17)},
               'S.G.P. fick genom dom av Högsta förvaltningsdomstolen den 20 '
               'juli 2010 rätt till halv sjukersättning för perioden augusti '
               '2006 - juni 2008. Försäkringskassan beslutade därefter den 17 '
               'augusti 2010 att S.G.P. inte hade rätt till någon '
               'utbetalning med anledning av domen.')
        self.t({'court': 'Skatterättsnämnden'},
               'I ansökan hos Skatterättsnämnden om förhandsbesked anförde X '
               'bl.a. följande. ')
        self.t({'court': 'Skattemyndigheten'},
               'Skattemyndigheten beslutade i två skilda beslut att påföra '
               'Bostadsaktiebolaget Poseidon ')
        self.t({'court': 'Skatterättsnämnden'},
               'I en ansökan hos Skatterättsnämnden om förhandsbesked '
               'anförde Advokat X AB och Advokat Y AB')

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

    def test_kamr(self):
        self.t({'court': 'kammarrättens'},
               'Bolaget överklagade och yrkade att kammarrätten skulle ändra '
               'länsrättens domar och undanröja')
        self.t({'court': 'kammarrätten'},
               'A-B.C. och A.C. överklagade och yrkade att kammarrätten, med '
               'ändring av länsrättens domar, skulle')
        self.t({'court': 'kammmarrätten'},
               'Skatteverket överklagade länsrättens dom hos kammarrätten och '
               'yrkade i första hand ')
        
    def test_hfd(self):
        self.t({'court': 'Regeringsrätten'},
               'I besvär hos Regeringsrätten yrkade X att förhandsbeskedet '
               'skulle ändras på så sätt att')
        self.t({'court': True},
               'Bolaget fullföljde sin talan.')
        self.t({'court': 'Regeringsrätten'},
               'Bolagen samt X och Y överklagade och yrkade att '
               'Regeringsrätten, med ändring av Skatterättsnämndens beslut, '
               'skulle')
        self.t({'court': True},
               'A-B.C. och dödsboet efter A.C. överklagade kammarrättens '
               'domar och anförde bl.a. följande. ')
        self.t({'court': True},
               'Skatteverket överklagade kammarrättens dom och yrkade att '
               'bolaget inte')

    def test_miv(self):
        self.t({'court': 'Migrationsverket'},
               'Migrationsverket beslutade den 14 februari 2006 att avslå '
               'M A B A:s ansökan om uppehållstillstånd m.m. samt att avvisa '
               'honom')
        self.t({'court': 'Migrationsverket'},
                'I sitt beslut den 6 augusti 2012 avslog Migrationsverket '
                'bl.a. A:s ansökan om uppehållstillstånd och avvisade honom '
                'från Sverige')

    def test_migr(self):
        self.t({'court': 'Migrationsverket'},
               'M A B A överklagade beslutet. Migrationsverket bestred... ')
        self.t({'court': 'Migrationsverket'},
               'A överklagade Migrationsverkets beslut i ersättningsfrågan '
               'till Länsrätten i Skåne län, migrationsdomstolen, som i dom '
               'den 21 oktober 2009 (ordförande Geijer) tillerkände A '
               'ersättning')

    def test_miod(self):
        self.t({'court': 'Migrationsverket'},
               'M A B A överklagade domen till Migrationsöverdomstolen. '
               'Migrationsverket bestred bifall till överklagandet.')
        self.t({'court': 'Migrationsverket'},
               'Migrationsverket överklagade domen till '
               'Migrationsöverdomstolen och yrkade att ')
        
