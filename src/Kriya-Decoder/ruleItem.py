## @author baskaran

import sys

from featureManager import FeatureManager
from languageModelManager import LanguageModelManager

class RuleItem(object):
    '''Phrase-table rule item (both lexical and hierarchical rules)'''

    __slots__ = "src", "tgt", "featVec", "score", "lm_heu"

    def __init__(self, src, tgt, featVec, score = 0.0, lm_heu = 0.0):
        self.src = src
        self.tgt = tgt
        self.featVec = featVec[:]
        self.score = score
        self.lm_heu = lm_heu

    @classmethod
    def initRule(cls, src, tgt, probs):
        term_count = 0
        for tgt_term in tgt.split():
            if tgt_term == 'X__1' or tgt_term == 'X__2': continue
            term_count += 1
        return RuleItem(src, tgt, FeatureManager.buildFeatVec(probs, term_count))

    @classmethod
    def initGlue(cls, src, tgt, probs):
        return RuleItem(src, tgt, [float(x) for x in probs.split()])

    @classmethod
    def initUNKRule(cls, unk_tok, featVec, score, lm_heu):
        return RuleItem(unk_tok, unk_tok, featVec, score, lm_heu)

    def getScore4TTL(self):
        return self.featVec[FeatureManager.getIndxP_ef()]

    def turnOffGlue(self):
        featVec[FeatureManager.getIndxGlue()] = 0.0

    def scoreRule(self):
        p_score = FeatureManager.scorePTEntry(self.featVec)
        lm_score = LanguageModelManager.scoreLMFeat(self.tgt)
        self.lm_heu = lm_score
        self.score = p_score + lm_score
