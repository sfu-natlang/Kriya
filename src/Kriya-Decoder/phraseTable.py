## @author baskaran

import math
import operator
import sys
import time

import settings
from hypothesis import Hypothesis
from myTrie import SimpleSuffixTree
from refPhrases import RefPhrases
from ruleItem import RuleItem

class PhraseTable(object):
    '''Phrase table class for containing the SCFG rules and serving associated queries'''

    tot_rule_pairs = 0
    src_trie = None
    ruleDict = {}
    __slots__ = "ttl"

    def __init__(self):
        '''Loading rules from the phrase table and initializing their feature values'''

        from settings import feat
        self.ttl = settings.opts.ttl

        self.loadRules()
        self.loadGlueRules()

    def delPT(self):
        del PhraseTable.ruleDict
        PhraseTable.src_trie = None

    def loadRules(self):
        '''Loads the filtered rules and filters them further by using the Suffix Tree of test data'''

        PhraseTable.tot_rule_pairs = 0
        prev_src = ''
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

                    if prev_src:
                        entriesLst.sort(key=operator.attrgetter("prob_e_f"), reverse=True)
                        PhraseTable.ruleDict[prev_src] = []
                        tgt_options = 0
                        for trans_option in entriesLst:
                            rule_obj = trans_option.rule
                            rule_obj.scoreRule()
                            PhraseTable.ruleDict[prev_src].append( rule_obj )
                            tgt_options += 1
                            if(self.ttl > 0 and tgt_options >= self.ttl): break
                        del entriesLst[:]

                rule = RuleItem.initRule(src, tgt, probs)
                entriesLst.append( TransOption(rule.getScore4TTL(), rule) )
                prev_src = src

            # Handle the last rule
            entriesLst.sort(key=operator.attrgetter("prob_e_f"), reverse=True)
            PhraseTable.ruleDict[prev_src] = []
            tgt_options = 0
            for trans_option in entriesLst:
                rule_obj = trans_option.rule
                rule_obj.scoreRule()
                PhraseTable.ruleDict[prev_src].append( rule_obj )
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

                (src, tgt, glue_val) = line.split(' ||| ')
                rule_obj = RuleItem.initGlue(src, tgt, float(glue_val))
                if (settings.opts.no_glue_penalty and src == 'S__1 X__2'):
                    rule_obj.turnOffGlue()

                rule_obj.scoreRule()
                PhraseTable.ruleDict[src] = []
                PhraseTable.ruleDict[src].append( rule_obj )
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
    def addUNKRule(cls, src_phr, rule_obj):
        cls.ruleDict[src_phr] = []
        cls.ruleDict[src_phr].append( rule_obj )

    @classmethod
    def findConsistentRules(cls, src_span):
        return SimpleSuffixTree.matchPattern(cls.src_trie, src_span)

    @classmethod
    def getTotalRules(cls):
        return cls.tot_rule_pairs


class TransOption(object):
    '''Translation option class for storing the rule and its p(e|f) probability'''

    __slots__ = "prob_e_f", "rule"

    def __init__(self, p_ef, r_obj):
        self.prob_e_f = p_ef
        self.rule = r_obj

