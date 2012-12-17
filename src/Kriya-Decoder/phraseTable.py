## @author baskaran

import math
import operator
import sys
import time

import settings
from entry_CP import Entry
from myTrie import SimpleSuffixTree
from lmKENLM import KENLangModel
from lmSRILM import SRILangModel
from refPhrases import RefPhrases

featVec = []

class PhraseTable(object):
    '''Phrase table class for containing the SCFG rules and serving associated queries'''

    tot_rule_pairs = 0
    src_trie = None
    ruleDict = {}
    __slots__ = "wVec", "ttl", "pp_val", "log_normalizer"

    def __init__(self):
        '''Loading rules from the phrase table and initializing their feature values'''

        from settings import feat
        self.wVec = feat
        self.ttl = settings.opts.ttl
        self.pp_val = math.log(2.718)
        self.log_normalizer = 0.434294

        tm_wgts_str = ' '.join( [str(x) for x in self.wVec.tm] )
        sys.stderr.write( "Weights are : [%s] %g %g %g\n" % (tm_wgts_str, self.wVec.wp, self.wVec.glue, self.wVec.lm) )

        self.loadRules()
        self.loadGlueRules()

    def delPT(self):
        del PhraseTable.ruleDict
        PhraseTable.src_trie = None

    def loadRules(self):
        '''Loads the filtered rules and filters them further by using the Suffix Tree of test data'''

        global featVec
        PhraseTable.tot_rule_pairs = 0
        prev_src = ''
        featVec = [0.0, 0.0, 0.0, 0.0, self.pp_val, 0.0, 0.0, 0.0]
        uniq_src_rules = 0
        entriesLst = []

        t_beg = time.time()
        rF = open(settings.opts.ruleFile, 'r')
        sys.stderr.write( "Loading SCFG rules from file     : %s\n" % (settings.opts.ruleFile) )
        try:
            for line in rF:
                line = line.strip()
                (src, tgt, probs) = line.split(' ||| ')                       # For Kriya phrase table
#                (src, tgt, f_align, r_align, probs) = line.split(' ||| ')     # For Moses phrase table

                if settings.opts.force_decode and not PhraseTable.tgtMatchesRef(tgt): continue
                if settings.opts.one_nt_decode and src.find('X__2') >= 0: continue
                PhraseTable.tot_rule_pairs += 1

                if prev_src != src:
                    uniq_src_rules += 1
                    if PhraseTable.src_trie is None:
                        PhraseTable.src_trie = SimpleSuffixTree(src, settings.opts.fr_rule_terms)
                    else:
                        PhraseTable.src_trie.addText(src)

                self.buildFeatVec(probs, tgt)

                if len(prev_src) > 0 and prev_src != src:
                    entriesLst.sort(key=operator.attrgetter("prob_e_f"), reverse=True)
                    PhraseTable.ruleDict[prev_src] = []
                    tgt_options = 0
                    for pt_item_obj in entriesLst:
                        entry_obj = pt_item_obj.entry_item
                        p_score = (self.wVec.tm[0] * entry_obj.featVec[0]) + (self.wVec.tm[1] * entry_obj.featVec[1]) + \
                                    (self.wVec.tm[2] * entry_obj.featVec[2]) + (self.wVec.tm[3] * entry_obj.featVec[3]) + \
                                    (self.wVec.tm[4] * entry_obj.featVec[4])+ (self.wVec.wp * entry_obj.featVec[5]) + \
                                    (self.wVec.glue * entry_obj.featVec[7])
                        lm_score = self.wVec.lm * self.getLMHeuScore(entry_obj.tgt)
                        entry_obj.lm_heu = lm_score
                        entry_obj.score = p_score + lm_score
                        PhraseTable.ruleDict[prev_src].append( entry_obj )
                        tgt_options += 1
                        if(self.ttl > 0 and tgt_options >= self.ttl): break
                    del entriesLst[:]

                entriesLst.append( PTableItem(featVec[2], Entry(0.0, 0.0, src, tgt, featVec, tgt)) )
                prev_src = src

            # Handle the last rule
            entriesLst.sort(key=operator.attrgetter("prob_e_f"), reverse=True)
            PhraseTable.ruleDict[prev_src] = []
            tgt_options = 0
            for pt_item_obj in entriesLst:
                entry_obj = pt_item_obj.entry_item
                p_score = (self.wVec.tm[0] * entry_obj.featVec[0]) + (self.wVec.tm[1] * entry_obj.featVec[1]) + \
                            (self.wVec.tm[2] * entry_obj.featVec[2]) + (self.wVec.tm[3] * entry_obj.featVec[3]) + \
                            (self.wVec.tm[4] * entry_obj.featVec[4])+ (self.wVec.wp * entry_obj.featVec[5]) + \
                            (self.wVec.glue * entry_obj.featVec[7])
                lm_score = self.wVec.lm * self.getLMHeuScore(entry_obj.tgt)
                entry_obj.lm_heu = lm_score
                entry_obj.score = p_score + lm_score
                PhraseTable.ruleDict[prev_src].append( entry_obj )
                tgt_options += 1
                if(self.ttl > 0 and tgt_options >= self.ttl): break
            del entriesLst[:]

        finally:
            rF.close()
            t_end = time.time()
            sys.stderr.write( "Unique source rules found                     : %d\n" % (uniq_src_rules) )
            sys.stderr.write( "Total pairs of SCFG rules loaded              : %d\n" % (PhraseTable.tot_rule_pairs) )
            sys.stderr.write( "Time taken for loading rules in dict and Trie : %1.3f sec\n\n" % (t_end - t_beg) )

        return None

    def buildFeatVec(self, probs, tgt_rule):
        '''Build the feature vector from a string of probs and add to it phrase & word penalty and glue score'''

        # All feature values must be represented as log-probs in base 'e'
        # Any log-prob in base '10' must be converted to base 'e' by dividing it by math.log10(math.exp(1)) i.e 0.434294
        global featVec
        term_count = 0

        # add the TM features
        featVec = [float(x) for x in probs.split()]                              # For using Kriya PT (for base-e log probs)
        #featVec = [float(x) / self.log_normalizer for x in probs.split()]        # For using Kriya PT (for base-10 log probs)

        #i = 0
        #for prob in probs.split():                                               # For using Moses phrase table
        #    if i < 4: featVec.append( math.log(float(prob)) )                    # probabilities are actual, so take log
        #    i += 1

        # add phrase penalty and word penalty to the featVec
        for tgt_term in tgt_rule.split():
            if tgt_term == 'X__1' or tgt_term == 'X__2': continue
            term_count += 1
        featVec += [self.pp_val, -term_count, 0.0, 0.0]

    def getLMHeuScore(self, tgt_rule):
        ''' Compute the LM Heuristic score for the target phrase '''

        lm_H = 0.0
        for tgt_term in tgt_rule.split():
            if tgt_term != 'X__1' and tgt_term != 'X__2':
                if settings.opts.use_srilm: lm_H += SRILangModel.queryLMlog10(tgt_term, 1)  # for SRILM wrapper
                else: lm_H += KENLangModel.queryLMlog10(tgt_term, 1)  # for KENLM wrapper
        return lm_H / self.log_normalizer

    def loadGlueRules(self):
        '''Loads the glue rules along with their feature values'''

        gF = open(settings.opts.glueFile, 'r')
        sys.stderr.write( "Loading Glue rules from file     : %s\n" % (settings.opts.glueFile) )
        try:
            for line in gF:
                line = line.strip()
                if line.startswith('#'): continue           # Ignore commented lines
                glueItems = line.split('#')                 # Handle and ignore any comments embedded on the same line
                line = glueItems[0].strip()

                (src, tgt, probs) = line.split(' ||| ')
                featVec = [float(x) for x in probs.split()]
                if (settings.opts.no_glue_penalty and src == 'S__1 X__2'):
                    featVec[7] = 0.0
                lm_score = self.wVec.lm * featVec[6]
                p_score = (self.wVec.tm[0] * featVec[0]) + (self.wVec.tm[1] * featVec[1]) + \
                            (self.wVec.tm[2] * featVec[2]) + (self.wVec.tm[3] * featVec[3]) + \
                            (self.wVec.tm[4] * featVec[4]) + (self.wVec.wp * featVec[5]) + \
                            lm_score + (self.wVec.glue * featVec[7])
                PhraseTable.ruleDict[src] = []
                PhraseTable.ruleDict[src].append( Entry(p_score, lm_score, src, tgt, featVec, tgt) )
        finally:
            gF.close()

    @classmethod
    def tgtMatchesRef(cls, tgt_phr):
        '''Check whether phrases in the target rules match the reference(s)'''

        tgtToks = tgt_phr.split()
        tgt_i = 0
        beg_pos = 0
        for tgt_tok in tgtToks:
            if tgt_tok == "X__1" or tgt_tok == "X__2":
                if tgt_i > 0 and tgt_i > beg_pos:
                    rule_phr = ' '.join( tgtToks[beg_pos:tgt_i] )
                    if not RefPhrases.isValidRefPhr(rule_phr):
                        return False
                beg_pos = tgt_i + 1
            tgt_i += 1

        if tgt_i > beg_pos:
            rule_phr = ' '.join( tgtToks[beg_pos:tgt_i] )
            if not RefPhrases.isValidRefPhr(rule_phr):
                return False
        return True

    @classmethod
    def tgtMatchesRefSent(cls, tgt_phr, sent_id):
        '''Check whether phrases in the target rules match the current set of reference sentence(s)'''

        tgtToks = tgt_phr.split()
        tgt_i = 0
        beg_pos = 0
        for tgt_tok in tgtToks:
            if tgt_tok == "S__1" or tgt_tok == "X__1" or tgt_tok == "X__2":
                if tgt_i > 0 and tgt_i > beg_pos:
                    rule_phr = ' '.join( tgtToks[beg_pos:tgt_i] )
                    if not RefPhrases.isValidRefPhrNSent(sent_id, rule_phr):
                        return False
                beg_pos = tgt_i + 1
            tgt_i += 1

        if tgt_i > beg_pos:
            rule_phr = ' '.join( tgtToks[beg_pos:tgt_i] )
            if not RefPhrases.isValidRefPhrNSent(sent_id, rule_phr):
                return False
        return True

    @classmethod
    def hasRule(cls, src_phr):
        '''Helper function for checking whether rules are found for a given source rule'''

        return cls.ruleDict.has_key(src_phr)

    @classmethod
    def getRuleEntries(cls, src_phr, sent_indx):
        '''Helper function for returning the rule entries for a given source rule'''

        #print "Total entries in ruleDict : ", len( cls.ruleDict[src_phr] )
        if settings.opts.force_decode:
            tgtLst = []
            for tgt_entry in cls.ruleDict[src_phr]:
                if cls.tgtMatchesRefSent(tgt_entry.tgt, sent_indx):
                    tgtLst.append( tgt_entry )
            return tgtLst
        else:
            return cls.ruleDict[src_phr]

    @classmethod
    def addUNKRule(cls, src_phr, entry_obj):
        cls.ruleDict[src_phr] = []
        cls.ruleDict[src_phr].append( entry_obj )

    @classmethod
    def findConsistentRules(cls, src_span):
        return SimpleSuffixTree.matchPattern(cls.src_trie, src_span)

    @classmethod
    def getTotalRules(cls):
        return cls.tot_rule_pairs


class PTableItem(object):
    '''Phrase table item class for temporarily handling  SCFG rules and serving associated queries'''

    __slots__ = "prob_e_f", "entry_item"

    def __init__(self, p_ef, e_obj):
        self.prob_e_f = p_ef
        self.entry_item = e_obj

