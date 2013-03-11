## @author baskaran

import sys

from featureManager import FeatureManager
from languageModelManager import LanguageModelManager

class RuleItem(object):
    '''Phrase-table rule item (both lexical and hierarchical rules)'''

    __slots__ = "src", "tgt", "sl_feat", "score", "lm_heu"

    def __init__(self, src, tgt, sl_f_obj, score = 0.0, lm_heu = 0.0):
        self.src = src
        self.tgt = tgt
        self.sl_feat = sl_f_obj
        self.score = score
        self.lm_heu = lm_heu

    @classmethod
    def initRule(cls, src, tgt, probs):
        term_count = 0
        for tgt_term in tgt.split():
            if tgt_term == 'X__1' or tgt_term == 'X__2': continue
            term_count += 1
        return RuleItem(src, tgt, FeatureManager.buildRuleFeats(probs, term_count))

    @classmethod
    def initGlue(cls, src, tgt, glue_val):
        return RuleItem(src, tgt, FeatureManager.buildGlueFeats(glue_val))

    @classmethod
    def initUNKRule(cls, unk_tok, featVec, score, lm_heu):
        return RuleItem(unk_tok, unk_tok, featVec, score, lm_heu)

    def getScoreSansLmHeu(self):
        return self.score - self.lm_heu

    def getScore4TTL(self):
        return FeatureManager.getScore4TTL(self.sl_feat)

    def turnOffGlue(self):
        FeatureManager.turnOffGlue(self.sl_feat)

    def scoreRule(self):
        p_score = FeatureManager.scorePTEntry(self.sl_feat)
        lm_score = LanguageModelManager.scoreLMFeat(self.tgt)
        self.lm_heu = lm_score
        self.score = p_score + lm_score

