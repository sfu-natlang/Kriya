#!/usr/bin/perl -w

# $ multi-sent-bleu.perl (computes sentence-level BLEU, aka BLEU+1) 2011-11-14 Hossein Hajimirsadeghi $
# $Id: multi-bleu.perl 3612 2010-10-11 11:32:27Z hieuhoang1972 $
use strict;

my $max_ngrams = 4;

my $stem = $ARGV[0];
my $NBest_file = $ARGV[1];
my $out_file = $ARGV[2];
if (scalar(@ARGV) == 4) {
    $max_ngrams = $ARGV[3];
}

if (!defined $stem) {
  print STDERR "usage: multi-sent-bleu.pl references hypothesis out_file\n";
  print STDERR "References could be comma separated or a single stem (will be expanded as reference0, reference1, ...)\n";
  exit(1);
}

my @REF;
if ($stem =~ /,/) {
    foreach my $ref_file (split(/,/, $stem)) {
        &add_to_ref($ref_file,\@REF);
    }
}
else {
    $stem .= ".ref" if !-e $stem && !-e $stem."0" && -e $stem.".ref0";

    my $ref=0;
    while(-e "$stem$ref") {
        &add_to_ref("$stem$ref",\@REF);
        $ref++;
    }
    &add_to_ref($stem,\@REF) if -e $stem;
}

open (HYP, $NBest_file) or die "Can't read $NBest_file";
open (OUT, ">$out_file") or die "Can't open $out_file for writing: $!";
my $sent_bleu;
while (<HYP>){
    chop;
    my @PARTS=split(/\s*\|\|\|\s*/,$_);
    my $Hyp = $PARTS[1];
    my $refNum = $PARTS[0];
    $Hyp =~ s/^\s+|\s+$//g;
    $Hyp =~ s/\s+/ /g;
    $sent_bleu = bleu1($Hyp, $REF[$refNum]);
    print OUT "$sent_bleu\n";
}
close(HYP);
close(OUT);


sub add_to_ref {
    my ($file, $REF) = @_;
    my $s=0;
    open(REF,$file) or die "Can't read $file";
    while(<REF>) {
        chop;
        s/^\s+|\s+$//g;
        s/\s+/ /g;
        push @{$$REF[$s++]}, $_;
    }
    close(REF);
}

sub bleu1 {
    my ($Hyp, $Ref) = @_;

    my @WORD = split(/ /,$Hyp);
    my $hyp_length = scalar(@WORD);

    my ($closest_diff, $closest_length) = (9999, 9999);
    my %REF_NGRAM = ();
    my @localCORRECT = (); #added by me
    my @localTOTAL = (); #added by me

    foreach my $reference (@{$Ref}) {
        #print "$s $_ <=> $reference\n";
        my @WORD = split(/ /, $reference);
        my $ref_length = scalar(@WORD);
        my $diff = abs($hyp_length - $ref_length);
        if ($diff < $closest_diff) {
            $closest_diff = $diff;
            $closest_length = $ref_length;
            # print STDERR "$s: closest diff ".abs($hyp_length-$ref_length)." = abs($hyp_length-$ref_length), setting len: $closest_length\n";
        } elsif ($diff == $closest_diff) {
            $closest_length = $ref_length if $ref_length < $closest_length;
            # from two references with the same closeness to me
            # take the *shorter* into account, not the "first" one.
        }
        for(my $n=1; $n<=4; $n++) {
            my %REF_NGRAM_N = ();
            for(my $start=0; $start<=$#WORD-($n-1); $start++) {
                my $ngram = "$n";
                for(my $w=0; $w<$n; $w++) {
                    $ngram .= " ".$WORD[$start+$w];
                }
                $REF_NGRAM_N{$ngram}++;
            }
            foreach my $ngram (keys %REF_NGRAM_N) {
                if (!defined $REF_NGRAM{$ngram} || $REF_NGRAM{$ngram} < $REF_NGRAM_N{$ngram}) {
                    $REF_NGRAM{$ngram} = $REF_NGRAM_N{$ngram};
                    #print "$i: REF_NGRAM{$ngram} = $REF_NGRAM{$ngram}<BR>\n";
                }
            }
        }
    }

    for(my $n=1; $n<=4; $n++) {
        my %T_NGRAM = ();
        for(my $start=0; $start<=$#WORD-($n-1); $start++) {
            my $ngram = "$n";
            for(my $w=0; $w<$n; $w++) {
                $ngram .= " ".$WORD[$start+$w];
            }
            $T_NGRAM{$ngram}++;
        }
        foreach my $ngram (keys %T_NGRAM) {
            $ngram =~ /^(\d+) /;
            my $n = $1;
            $localTOTAL[$n] += $T_NGRAM{$ngram};
            if (defined($REF_NGRAM{$ngram})) {
                if ($REF_NGRAM{$ngram} >= $T_NGRAM{$ngram}) {
                    $localCORRECT[$n] += $T_NGRAM{$ngram}; #added by me
                }
                else {
                    $localCORRECT[$n] += $REF_NGRAM{$ngram}; #added by me
                }
                #print "### $ngram ||| $localCORRECT[$n] ||| $localTOTAL[$n]\n";
            }
            #else {
            #    print "# $ngram ||| $localTOTAL[$n]\n";
            #}
        }
    }

    #added by me
    my $local_brevity_penalty = 1;
    my @localbleu = ();
    for(my $n=1; $n<=4; $n++) {
        if (defined($localTOTAL[$n])) {
            if ($n ==1) {
                if (defined($localCORRECT[$n])) {
                    $localbleu[$n]=$localTOTAL[$n]?$localCORRECT[$n]/$localTOTAL[$n]:0;
                    #print ">>> $n :: $localCORRECT[$n] ** $localTOTAL[$n] ||| $localbleu[$n]\n";
                } else {
                    $localbleu[$n]=0;
                }
            } else {
                if (defined($localCORRECT[$n])) {
                    #$localbleu[$n]=$localTOTAL[$n]?($localCORRECT[$n]+1)/($localTOTAL[$n]+1):0;
                    $localbleu[$n]=($localCORRECT[$n]+1)/($localTOTAL[$n]+1);
                } else {
                    $localbleu[$n]=1/($localTOTAL[$n]+1);
                }
            }
        } else {
            #$localbleu[$n]=0;
            $localbleu[$n]=1;
        }
    }

    if ($closest_length == 0) {
        printf "BLEU = 0, 0/0/0/0 (BP=0, ratio=0, hyp_len=0, ref_len=0)\n";
        exit(1);
    }

    if ($hyp_length < $closest_length) {
        $local_brevity_penalty = exp(1-$closest_length/$hyp_length);
    }

    my $n_bleu = 0;
    for (my $j=1; $j<=$max_ngrams; $j++) {
        $n_bleu += my_log($localbleu[$j]);
    }
    #print "$local_brevity_penalty ** $localbleu[1]  ", my_log($localbleu[1]), " || $localbleu[2]  ", my_log($localbleu[2]), " || $localbleu[3]  ", my_log($localbleu[3]), " || $localbleu[4]  ", my_log($localbleu[4]), "\n";
    my $bleu = $local_brevity_penalty * exp($n_bleu / $max_ngrams);

    #my $bleu = $local_brevity_penalty * exp((my_log( $localbleu[1] ) +
    #                                    my_log( $localbleu[2] ) +
    #                                    my_log( $localbleu[3] ) +
    #                                    my_log( $localbleu[4] ) ) / 4) ;

    return ($bleu);
    #end of added by me
}

sub my_log {
  return -9999999999 unless $_[0];
  return log($_[0]);
}
