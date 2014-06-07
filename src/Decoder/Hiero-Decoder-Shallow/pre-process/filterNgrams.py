## This program filters the english-gigaword LM for up to 3-grams ##


import sys, gzip


N_GRAMS = 3        # N-gram size for filtering


def filterNgrams(ngramFileIn, ngramFileOut):
    '''Filter the ngrams in in-file for up to n = N_GRAMS and write to out-file'''

    global N_GRAMS
    line_count = 0
    ngram_count = 0

    inZ = gzip.open(ngramFileIn, 'r')
    outZ = gzip.open(ngramFileOut, 'w')
    while True:
        line = inZ.readline()
        line = line.strip()
        if line == '': break           # Exit the loop at the last line

        line_count += 1
        (ngram, count) = line.split('\t')
        if len(ngram.split(' ')) <= N_GRAMS:
            outZ.write( "%s\n" % (line) )
            ngram_count += 1

    inZ.close()
    outZ.close()
    print "Total # of n-grams found    : %d" %line_count
    print "Total # of n-grams filtered : %d" % ngram_count


def main():
    ngramFileIn = sys.argv[1]
    ngramFileOut = sys.argv[2]
    if ngramFileIn == ngramFileOut:
        print "Specify different files for input and output. Exiting!!"
        sys.exit()

    filterNgrams(ngramFileIn, ngramFileOut)


if __name__ == '__main__':
    main()
