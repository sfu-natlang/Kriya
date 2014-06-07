#!/usr/bin/env python3
# -*- coding:utf-8-unix -*-
###
### RIBES.py - RIBES (Rank-based Intuitive Bilingual Evaluation Score) scorer
### Copyright (C) 2011  Nippon Telegraph and Telephone Corporation
### 
### This program is free software; you can redistribute it and/or
### modify it under the terms of the GNU General Public License
### as published by the Free Software Foundation; either version 2
### of the License, or (at your option) any later version.
### 
### This program is distributed in the hope that it will be useful,
### but WITHOUT ANY WARRANTY; without even the implied warranty of
### MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
### GNU General Public License for more details.
### 
### You should have received a copy of the GNU General Public License
### along with this program; if not, write to the Free Software
### Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
### 
##  History
##  version 1.02.3 (2012/2/23) Fixed a problem in output
##  version 1.02.2 (2011/10/25) Fixed a problem without -o option (in systems without /dev/stdout)
##  version 1.02.1 (2011/8/18) Fixed bug on bytes.decode
##  version 1.02 (2011/8/16) Improved distinguishment of same words, with a little code refactoring
##  version 1.01 (2011/8/10) Fixed bug on empty lines
##  version 1.0  (2011/8/1)  Initial release
#
# Reference:
#  Hideki Isozaki, Tsutomu Hirao, Kevin Duh, Katsuhito Sudoh, and Hajime Tsukada,
#  "Automatic Evaluation of Translation Quality for Distant Language Pairs",
#  Proceedings of the 2010 Conference on Empirical Methods in Natural Language Processing (EMNLP),
#  pp. 944--952 Cambridge MA, October, 2010
#  -- http://aclweb.org/anthology-new/D/D10/D10-1092.pdf
#

import os,sys,re
import datetime
import traceback
from optparse import OptionParser
from math import exp

_RIBES_VERSION = '1.02.3'
debug = 0

multiws_pattern = re.compile(r'\s+')

### calculate Kendall's tau
def kendall(ref, hyp):
    """Calculates Kendall's tau between a reference and a hypothesis

    Calculates Kendall's tau (also unigram precision and brevity penalty (BP))
    between a reference word list and a system output (hypothesis) word list.

    Arguments:
        ref : list of reference words
        sub : list of system output (hypothesis) words

    Returns:
        A tuple (nkt, precision, bp)
            - nkt       : normalized Kendall's tau
            - precision : unigram precision
            - bp        : brevity penalty

    Raises:
        RuntimeError: reference has no words, possibly due to a format violation
    """

    # check reference length, raise RuntimeError if no words are found.
    if len(ref) == 0:
        raise RuntimeError ("Reference has no words")
    # check hypothesis length, return "zeros" if no words are found
    elif len(hyp) == 0:
        return (0.0, 0.0, 0.0)

    # calculate brevity penalty (BP), not exceeding 1.0
    bp = min(1.0, exp(1.0 - 1.0 * len(ref)/len(hyp)))

    
    ### determine which ref. word corresponds to each hypothesis word
    # list for ref. word indices
    intlist = []


    ### prepare helper pseudo-string representing ref. and hyp. word sequences as strings,
    ### by mapping each word into non-overlapping Unicode characters
    # Word ID (dictionary)
    worddict = {}
    # Unicode hexadecimal sequences for ref. and words
    _ref = ""
    _hyp = ""
    for w in ref:
        # if w is not found in dictironary "worddict", add it.
        if w not in worddict:
            worddict[w] = len(worddict)
        # append Unicode hexadecimal for word w (with offset of 0x4e00 -- CJK character range)
        _ref += str(hex(worddict[w] + 0x4e00)).replace('0x', '', 1)
    # decode Unicode (UTF-16 BigEndian) sequences to UTF-8
    if sys.version_info.minor > 1:
        mapped_ref = bytes.fromhex(_ref).decode(encoding="utf_16_be")
    else:
        mapped_ref = bytes.fromhex(_ref).decode("utf_16_be")

    for w in hyp:
        # if w is not found in dictironary "worddict", add it.
        if w not in worddict:
            worddict[w] = len(worddict)
        # append Unicode hexadecimal for word w (with offset of 0x4e00 -- CJK character range)
        _hyp += str(hex(worddict[w] + 0x4e00)).replace('0x', '', 1)
    # decode Unicode (UTF-16 BigEndian) sequences to UTF-8
    if sys.version_info.minor > 1:
        mapped_hyp = bytes.fromhex(_hyp).decode(encoding="utf_16_be")
    else:
        mapped_hyp = bytes.fromhex(_hyp).decode("utf_16_be")

    for i in range(len(hyp)):
        ### i-th hypthesis word hyp[i]
        
        if not hyp[i] in ref: 
            ### hyp[i] doesn't exist in reference
            pass
            # go on to the next hyp. word
        elif ref.count(hyp[i]) == 1 and hyp.count(hyp[i]) == 1:
            ### if we can determine one-to-one word correspondence by only unigram
            ### one-to-one correspondence
            # append the index in reference
            intlist.append(ref.index(hyp[i]))
            # go on to the next hyp. word
        else:
            ### if not, we consider context words...
            # use Unicode-mapped string for efficiency
            for window in range (1, max(i, len(hyp)-i)):
                if window <= i:
                    ngram = mapped_hyp[i-window:i+1]
                    if mapped_ref.count(ngram) == 1 and mapped_hyp.count(ngram) == 1:
                        intlist.append(mapped_ref.index(ngram) + len(ngram) -1)
                        break
                if i+window < len(hyp):
                    ngram = mapped_hyp[i:i+window+1]
                    if mapped_ref.count(ngram) == 1 and mapped_hyp.count(ngram) == 1:
                        intlist.append(mapped_ref.index(ngram))
                        break

    ### At least two word correspondences are needed for rank correlation
    n = len(intlist)
    if n == 1 and len(ref) == 1:
        return (1.0, 1.0/len(hyp), bp)
    elif n < 2:
        # if not, return score 0.0
        return (0.0, 0.0, bp)

    ### calculation of rank correlation coefficient
    # count "ascending pairs" (intlist[i] < intlist[j])
    ascending = 0.0
    for i in range(len(intlist)-1):  
        for j in range(i+1,len(intlist)):
            if intlist[i] < intlist[j]:
                ascending += 1

    # normalize Kendall's tau
    nkt = ascending / ((n * (n - 1))/2)

    # calculate unigram precision
    precision = 1.0 * n / len(hyp)

    # return tuple (Normalized Kendall's tau, Unigram Precision, and Brevity Penalty)
    return (nkt, precision, bp)
    

class RIBESevaluator:
    """RIBES evaluator class.

    Receives "Corpus" instances and score them with hyperparameters alpha and beta.

    Attributes (private):
        __sent   : show sentence-level scores or not
        __alpha  : hyperparameter alpha, for (unigram_precision)**alpha
        __beta   : hyperparameter beta,  for (brevity_penalty)**beta
        __output : output file name
    """
    def __init__ (self, sent=False, alpha=0.25, beta=0.10, output=sys.stdout):
        """Constructor.

        Initialize a RIBESevaluator instance with four attributes. All attributes have their default values.

        Arguments (Keywords):
            - sent   : for attribute __sent,   default False
            - alpha  : for attribute __alpha,  default 0.25
            - beta   : for attribute __beta,   default 0.10
            - output : for attribute __output, default sys.stdout
        """
        self.__sent   = sent
        self.__alpha  = alpha
        self.__beta   = beta
        self.__output = output


    def eval (self, hyp, REFS):
        """Evaluate a system output with multiple references.

        Calculates RIBES for a system output (hypothesis) with multiple references,
        and returns "best" score among multi-references and individual scores.
        The scores are corpus-wise, i.e., averaged by the number of sentences.

        Arguments:
            hyp  : "Corpus" instance of hypothesis
            REFS : list of "Corpus" instances of references

        Returns:
            A tuple (_best_ribes_acc, _RIBES_ACC)
                - _best_ribes_acc : best corpus-wise RIBES among multi-reference
                - _RIBES_ACC      : list of corpus-wise RIBES for each reference

        Raises:
            RuntimeError : #sentences of hypothesis and reference doesn't match
            RuntimeError : from the function "kendall"
        """

        for ref in REFS:
            # check #sentences of hypothesis and each of the multi-references
            if len(hyp) != len(ref):
                raise RuntimeError ( "Different #sentences between " + hyp.filename + " (" + str(len(hyp)) + "sents.) and " + ref.filename + "( " + str(len(ref)) + "sents.)")

        # initialize "best" corpus-wise score
        _best_ribes_acc = 0.0
        # initialize individual corpus-wise score list
        _RIBES_ACC = [ 0.0 ] * len(REFS)

        # scores each hypothesis
        for i in range (len(hyp)):
            # initialize "best" sentence-wise score
            _best_ribes = 0.0

            # for each reference
            for r in range(len(REFS)):
                try:
                    # calculate Kendall's tau, unigram precision, and brevity penalty.
                    (nkt, precision, bp) = kendall(REFS[r][i], hyp[i])
                except Exception as e:
                    # if the function "kendall" raises an exception, throw toward the main function
                    print ("Error in " + REFS[r].filename + " line " + str(i), file=sys.stderr)
                    raise e

                # RIBES = (normalized Kendall's tau) * (unigram_precision ** alpha) * (brevity_penalty ** beta)
                _ribes = nkt * (precision ** self.__alpha) * (bp ** self.__beta)
                # accumulate RIBES for "individual" corpus-wise score for (r+1)-th reference
                _RIBES_ACC[r] += _ribes / len(hyp)
                # maintain the best sentence-wise score
                if _ribes > _best_ribes:
                    _best_ribes = _ribes

            # accumulate the "best" sentence-wise score for the "best" corpus-wise score
            _best_ribes_acc += _best_ribes / len(hyp)

            # print "best" sentence-wise score if __sent is True
            if self.__sent and self.__output != None:
                print ("%.6f alpha=%f beta=%f %s sentence %d" % (_best_ribes, self.__alpha, self.__beta, hyp.filename, i), file=self.__output)

        # returns the tuple of the "best" corpus-wise RIBES and score list for each reference
        return (_best_ribes_acc, _RIBES_ACC)


class Corpus:
    """Corpus class.

    Stores sentences and is used for evaluation.

    Attributes (private):
        __sentence : list of sentences (word lists)
        __numwords : #words in the corpus (currently not used but can be used for corpus statistics.)

    Attributes (public):
        filename   : corpus file name (set as public for error messages about the corpus)
    """
    def __init__ (self, _file, case=False, encoding="utf-8"):
        """Constructor.

        Initialize a Corpus instance by a corpus file with a certain encoding (default utf-8).

        Argument:
            _file : corpus file of "sentence-per-line" format
        Keyword:
            case     : preserve uppercase letters or not, default: False
            encoding : corpus file encoding, default: utf-8
        """

        # initialize contents
        self.__sentence = []
        self.__numwords = 0

        # set file name
        self.filename = _file

        # read corpus
        with open (_file, encoding=encoding) as fp:
            for line in fp:
                # eliminates unnecessary spaces (white spaces and tabs) in each sentence
                line = multiws_pattern.sub(r' ', line.strip())

                # lowercasing if case is False
                if not case:
                    line = line.lower()

                # split the sentence to a word list and append it to the corpus sentence list
                self.__sentence.append( line.split() )

                # count words
                self.__numwords += len(self.__sentence[-1])

    def __len__ (self):
        """Corpus size.

        Returns:
            len(self.__sentence) : corpus size (#sentences)
        """
        return len(self.__sentence)

    def __getitem__ (self, index):
        """Pick up a sentence in the corpus

        Argument:
            index : index of the sentence to pick up

        Returns:
            self.__sentence[index] : (index+1)-th sentence in the corpus

        Raises:
            IndexError : index exceeds the size of the corpus
        """
        if len(self.__sentence)-1 < index:
            raise IndexError ( "Invalid index " + str(index) + " for list of " + str(len(self.__sentence)) + " sentences" )
        else:
            return self.__sentence[index]

###
### wrapper function for output
###
def outputRIBES (options, args, file=sys.stdout):
    # print start time
    print ("# RIBES evaluation start at " + str(datetime.datetime.today()), file=sys.stderr)

    # initialize "RIBESevaluator" instance
    evaluator = RIBESevaluator (sent=options.sent, alpha=options.alpha, beta=options.beta, output=file)

    # REFS : list of "Corpus" instance (for multi reference)
    REFS = []

    for _ref in options.ref:
        if debug > 0:
            # print reference file name (if debug > 0)
            print ("# reference file [" + str(len(REFS)) + "] : " + _ref, file=file)

        # read multi references, construct and store "Corpus" instance
        REFS.append( Corpus(_ref, case=options.case, encoding=options.encoding) )

    for i in range(len(args)):
        if debug > 0:
            # print system output file name (if debug > 0)
            print ("# system output file [" + str(i) + "] : " + args[i], file=file)

        # read system output and construct "Corpus" instance
        result = Corpus(args[i], case=options.case, encoding=options.encoding)

        # evaluate by RIBES -- "best_ribes" stands for the best score by multi-references, RIBESs stands for the score list for each references
        (best_ribes, RIBESs) = evaluator.eval (result, REFS)

        # print resutls
        print ("%.6f alpha=%f beta=%f %s" % (best_ribes, options.alpha, options.beta, args[i]), file=file)

    # print end time
    print ("# RIBES evaluation done at " + str(datetime.datetime.today()), file=sys.stderr)


###
### main function
###
def main ():
    # variable "debug" is global...
    global debug

    usage = "%prog [options] system_outputs"
    optparser = OptionParser(usage)

    ### option definitions
    # -d/--debug : debug level (0: scores and start/end time, 1: +ref/hyp files)
    optparser.add_option("-d", "--debug",    dest="debug",    default=0,                          type="int",    help="debug level",                         metavar="INT")

    # -r/--ref : reference (multiple references available, repeat "-r REF" in arguments)
    optparser.add_option("-r", "--ref",      dest="ref",      default=[],    action="append",     type="string", help="reference translation file (use multiple \"-r REF\" for multi-references)",          metavar="FILE")

    # -c/--case : preserve uppercase letters
    optparser.add_option("-c", "--case",     dest="case",     default=False, action="store_true",                help="preserve uppercase letters in evaluation (default: False -- lowercasing all words)")

    # -s/--sentence : show scores for every sentences
    optparser.add_option("-s", "--sentence", dest="sent",     default=False, action="store_true",                help="output scores for every sentences")

    # -a/--alpha : "Unigram Precison" to the {alpha}-th power
    optparser.add_option("-a", "--alpha",    dest="alpha",    default=0.25,                       type="float",  help="hyperparameter alpha (default=0.25)", metavar="FLOAT")

    # -b/--beta : "Brevity Penalty" to the {beta}-th power
    optparser.add_option("-b", "--beta",     dest="beta",     default=0.10,                       type="float",  help="hyperparameter beta  (default=0.10)", metavar="FLOAT")

    # -e/--encoding : file encoding
    optparser.add_option("-e", "--encoding", dest="encoding", default="utf-8",                    type="string", help="file encoding",                       metavar="ENCODING")

    # -o/--output : output file
    optparser.add_option("-o", "--output",   dest="output",   default="",              type="string", help="log output file",                     metavar="FILE")

    # args : system outputs

    # parse options
    (options, args) = optparser.parse_args()

    # set debug level (global)
    debug = options.debug

    if len(options.output) == 0:
        # output to stdout
        outputRIBES (options, args)
    else:
        # output file is automatically closed ...
        with open (options.output, 'w') as ofp:
            outputRIBES (options, args, file=ofp)



if __name__ == "__main__":
    try:
        main()
    except Exception as err:
        traceback.print_exc(file=sys.stderr)
        sys.exit(255)
