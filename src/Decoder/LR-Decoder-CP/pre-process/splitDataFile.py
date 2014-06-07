## This program splits the data-file into different parts having some specific # of sentences ##
## The no of sentences in each file is specified by a global constant ##

import sys, os

# Constants
outDir = ''
out_suffix = '.out'
SENT_PER_FILE = 100

def splitSpanFile(inFile):

    global SENT_PER_FILE
    j = 1
    sent_count = 0
    sentLst = []

    inF = open(inFile, 'r')
    for line in inF:
        line = line.strip()
        sentLst.append(line)
        sent_count += 1

        if len(sentLst) % SENT_PER_FILE == 0:
            write2File(j, sentLst)
            del sentLst[:]
            j += 1
    inF.close()

    remaining_sentences = len(sentLst)
    if remaining_sentences > 0:
        if 2 * remaining_sentences >= SENT_PER_FILE:
            write2File(j, sentLst)
        else:
            write2File(j-1, sentLst, True)
        del sentLst[:]

def write2File(j, sentLst, append_2_file=False):

    global outDir
    global out_suffix
    outFile = outDir + str(j) + out_suffix
    if append_2_file:
        outF = open(outFile, 'a')
        print 'Appending to file: ', outFile
    else:
        outF = open(outFile, 'w')
        print 'Writing to file  : ', outFile

    for sent in sentLst:
        outF.write("%s\n" % (sent))
    outF.close()

def main():

    global outDir
    global SENT_PER_FILE
    inFile = sys.argv[1]
    outDir = sys.argv[2]
    if( len(sys.argv) == 4 ):
        SENT_PER_FILE = int( sys.argv[3] )
    if not outDir.endswith('/'): outDir += '/'

    splitSpanFile(inFile)


if __name__ == '__main__':
    main()
