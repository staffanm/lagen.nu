# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from ferenda.testutil import RepoTester, parametrize_repotester
from ferenda.testutil import Py23DocChecker
import doctest
import unittest
from datetime import date

# SUT
import dv


class TestDV(RepoTester):
    repoclass = dv.DV
    docroot = "../../ferenda/test/files/repo/dv"
parametrize_repotester(TestDV)


class TestDVUnit(unittest.TestCase):

    def doctest(self):
        """
        exmmple:
        
            >>> # 2003_not_1
            >>> is_instans(None, "Den 9:e. 1. (Ö 4629-01) V.B. och D.B. mot RÅ ang. resning. V.B. och D.B., som är bröder, åtalades vid Sollentuna TR för mord alternativt medhjälp till mord.")
            True
            >>> is_instans(None, "HD: Skäl. I resningsansökningarna har V.B. och D.B. åberopat bestämmelsen i 58:2 4 RB")
            True
            >>> # 2003_not_11
            >>> is_instans(None, "Den 6:e. 11. (Ö 52-03) K.P. ang. avvisande av stämningsansökan. K.P. ansökte i Svea HovR om att stämning skulle utfärdas mot H.S., f.d. lagman i Falu TR.")
            >>> # 2003_not_18
            >>> is_instans(None, "Den 14:e. 18. (T 4958-98) M.P. mot Trygg-Hansa Trygg-Hansa ang. trafikskadeersättning. M.P. yrkade i Stockholms TR att TR:n skulle fastställa att...")
            >>> # 2008_not_51
            >>> is_instans(None, "<em>Stockholms tingsrätt dömde</em>den 5 oktober 2007 F.T. för förseelse mot yrkestrafikförordningen m.m. till penningböter")
            >>> # 2008_not_52
            >>> is_instans(None, "Huddinge tingsrätt förordnade den 4 november 1992 att C.T. skulle ha ensam vårdnad om dottern.")
            """
    def test_plain_courtname(self):
        self.assertEqual({'court': 'Örebro tingsrätt'},
                         dv.analyze_instans('Örebro tingsrätt'))
        self.assertEqual({'court': 'Hovrätten över Skåne och Blekinge'},
                         dv.analyze_instans('Hovrätten över Skåne och Blekinge'))
        self.assertEqual({'court': 'Högsta domstolen'},
                         dv.analyze_instans('Högsta domstolen'))

    def test_not_courtname(self):
        self.assertEqual({},
                         dv.analyze_instans('Jönköpings tingsrätt beslutade att...'))

    def test_fr_forstainstans(self):
        self.assertEqual({'court': 'Försäkringskassan',
                          'date': date(2010, 8, 17)},
                         dv.analyze_instans('S.G.P. fick genom dom av Högsta förvaltningsdomstolen den 20 juli 2010 rätt till halv sjukersättning för perioden augusti 2006 - juni 2008. Försäkringskassan beslutade därefter den 17 augusti 2010 att S.G.P. inte hade rätt till någon utbetalning med anledning av domen.'))

    def test_fr_yttrade(self):
        self.assertEqual({'court': 'Förvaltningsrätten i Göteborg',
                          'date': date(2011, 4, 21),
                          'constitution': [{'name': 'Hasselberg',
                                            'position': 'ordförande'}]},
                         dv.analyze_instans('Förvaltningsrätten i Göteborg (2011-04-21, ordförande Hasselberg) yttrade: Tillämplig bestämmelse'))
        self.assertEqual({'court': 'Kammarrätten i Göteborg',
                          'date': date(2011, 11, 2),
                          'constitution': [{'name': 'Nyström'},
                                           {'name': 'Nilsson', 'position': 'referent'},
                                           {'name': 'Sjögren Samuelsson'}]},
                         dv.analyze_instans('Kammarrätten i Göteborg (2011-11-02, Nyström, Nilsson, referent, Sjögren Samuelsson) yttrade: Frågan i målet är...'))
        self.assertEqual({'court': 'Högsta förvaltningsdomstolen',
                          'date': date(2013, 5, 27),
                          'constitution': [{'name': 'Jermsten'},
                                           {'name': 'Dexe'},
                                           {'name': 'Silfverberg'},
                                           {'name': 'Bull'}]},
                         dv.analyze_instans('Högsta förvaltningsdomstolen (2013-05-27, Jermsten, Dexe, Silfverberg, Bull) yttrade:'))
    

    
            
