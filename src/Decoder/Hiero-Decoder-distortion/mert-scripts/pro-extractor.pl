#!/usr/bin/perl -w

use Math::Round;

# Modified by Baskaran Sankaran in Oct/Nov 2012 #
#   * Added support for RIBES (in addition to existing BLEU and TER)
#   * Added support for BLEU-1 and METEOR
# Modified by Baskaran Sankaran in Mar 2012 #
#   * Retains unique candidates while merging the current n-best list with previous lists (duplicates are discarded)
# Modified by Baskaran Sankaran in Dec 2011 #
#   i) also extracts the features from the N-best list in a format similar to Moses #
#  ii) fixes some minor bugs and some consistency changes #
#  Code uses some parts as taken from Moses scripts for peeking the N-best list #

my $stem = undef;
my $run = undef;
my $set_id = undef;
my $work_dir = undef;
my $metric = undef;
my $nbest_hist = undef;
my $round_scores = 1;
my $is_multi_obj = 0;
my $multi_obj_style = undef;
my $comb_wgts = undef;
my $retain_all_hyp = 0;
my $closest_length;
my %REF_NGRAM;
my $usage = 0;
my $ter_parallel_cmd;
my $meteor_parallel_cmd;
my $collate_scrpt;
my $pareto_scrpt;
my $lin_comb_scrpt;
my $sent_bleu_scrpt;
my $sent_ribes_scrpt;
my $pareto_out;
my $pareto_clsfr;
my $lin_comb_out;

use strict;
use Cwd 'abs_path';
use File::Basename;
use Getopt::Long;

GetOptions(
    "refs=s" => \$stem,
    "run=i" => \$run,
    "set-id=s" => \$set_id,
    "work-dir=s" => \$work_dir,
    "metric=s" => \$metric,
    "nbest-hist=s" => \$nbest_hist,
    "multi-obj" => \$is_multi_obj,
    "multi-obj-style=s" => \$multi_obj_style,
    "comb-wgts=s" => \$comb_wgts,
    "retain-all-hyp" => \$retain_all_hyp,
    "help" => \$usage
) or exit(1);

if ($usage || !defined $stem || !defined $run || !defined $work_dir) {
    print STDERR "Usage: ".basename($0)." --refs=<references> --run=<run_id> --set-id=<set-id> --work-dir=<MERT Working dir>
Options:
  --refs=STRING ... set of comma separated reference files
  --run=N ... current iteration number
  --set-id=STRING ... unique set id indicating where the tuning/ test set sentences come from; for TER (default Kriya-PRO)
  --work-dir=mert-dir ... where to find the N-best files
  --metric=STRING ... what metric to use (BLEU, RIBES and TER are supported presently)
  --nbest-hist=STRING ... n-best history file
  --multi-obj ... boolean flag for indicating that it is multi-objective tuning (default false)
  --multi-obj-style=STRING ... Multi-objective tuning style (multi-obj must be true)
  --comb-wgts ... combination weights (colon separated) for the linear combination and pareto style multi-objective
  --retain-all-hyp ... boolean flag for retaining all hypotheses including duplicates (default false)
  --help ... prints this message
\n";
exit(1);
}

if (!defined $metric) {
    $metric = "BLEU";
    print STDERR "INFO: Using the default metric $metric.\n";
}
else {
    if (!$is_multi_obj) {
        my $lc_met = lc($metric);
        if($lc_met ne "bleu" && $lc_met !~ /bleu\d/ && $lc_met ne "meteor" && $lc_met ne "ribes" && $lc_met ne "ter") {
            die "ERROR: Metric $metric isn't supported. Exiting!!\n";
        }
        if ($lc_met =~ /bleu(\d)/) { $metric = "BLEU$1"; }
        $metric = "BLEU" if $lc_met eq "bleu";
        $metric = "METEOR" if $lc_met eq "meteor";
        $metric = "RIBES" if $lc_met eq "ribes";
        $metric = "TER" if $lc_met eq "ter";
    }
}

die "ERROR: Working dir $work_dir doesn't exist. Exiting!!\n" if(!-d $work_dir);
if (defined $multi_obj_style && $multi_obj_style =~ /linear-comb|pareto/ && !defined $comb_wgts) {
    die "Set --comb-wgts (colon separated weights) options for linear-combination. Exiting!!\n";
}

if($is_multi_obj) {
    $multi_obj_style = "ensemble" if (!defined $multi_obj_style);
}

if (!defined $set_id) { 
    $set_id = "Kriya-PRO";
    print STDERR "INFO: Using default value of 'Kriya-PRO' for set-id\n";
}

#if(!defined $ENV{TER_DIR}) { die "**ERROR: Needs the Environmental variable TER_DIR to be defined. Exiting!!\n"; }

$collate_scrpt = abs_path(dirname($0))."/collate_scores.sh";
$pareto_scrpt = abs_path(dirname($0))."/ParetoFrontier.py";
$lin_comb_scrpt = abs_path(dirname($0))."/LinearCombination.py";
$meteor_parallel_cmd = abs_path(dirname($0))."/sentence-METEOR.pl";
$ter_parallel_cmd = abs_path(dirname($0))."/sentence-TER.pl";
$sent_bleu_scrpt = abs_path(dirname($0))."/multi-sent-bleu.perl";
$sent_ribes_scrpt = abs_path(dirname($0))."/multi-sent-ribes.perl";

$work_dir =~ s/\/$//;
my $out_dir = "${work_dir}/Metrics-stats";
if(!-d $out_dir) { safesystem("mkdir -p $out_dir"); }
#else { safesystem("rm $out_dir/*"); }

my $cmd;
my $tot_sents;
my $new_cands;
my $met_file;
my $scores_file;
my %candCntHsh = ();
my $new_cands_file = "${work_dir}/run${run}.nbest.new";
my $NBest_file = "${work_dir}/run${run}.nbest.out";
my $feat_hist = "${work_dir}/all.features.dat";
$nbest_hist = "${work_dir}/all.nbest.out";
$pareto_out = "${work_dir}/run${run}.pareto.out";
$pareto_clsfr = "${out_dir}/pareto.out.pareto";
$lin_comb_out = "${out_dir}/lincomb.out.lincomb";

if ($run > 1 && !-e $feat_hist) {
    #if (-e $nbest_hist) { safesystem("rm $nbest_hist"); }
    #if (-e $feat_hist) { safesystem("rm $feat_hist"); }
    my $prev_run = 0;
    while ($prev_run < $run) {
        $prev_run++;
        my $prev_NBest_file = "${work_dir}/run${prev_run}.nbest.out";
        my $prev_new_cands_file = "${work_dir}/run${prev_run}.nbest.new";
        ($tot_sents, $new_cands) = xtract_new_and_merge($nbest_hist, $prev_NBest_file, $prev_new_cands_file);
        printf STDERR "Total new candidates added in iteration %2d : %d\n", $prev_run, $new_cands;

        xtract_feats($nbest_hist, $feat_hist);
        if ($new_cands > 0) {
            if (($is_multi_obj && $metric =~ /ter/i) || $metric eq "TER") {
                $met_file = "$out_dir/ter.out.ter";
                safesystem("cp $met_file ${met_file}.bak") if (-e $met_file);
                my $ter_scores_ref = read_metric_scores('TER', $met_file, \%candCntHsh);
                TER_Sent($run, $stem, $prev_new_cands_file, $met_file, $out_dir, $ter_scores_ref);
                print "Finished getting TER stats ...\n";
            }
            if (($is_multi_obj && $metric =~ /meteor/i) || $metric eq "METEOR") {
                $met_file = "$out_dir/meteor.out.meteor";
                safesystem("cp $met_file ${met_file}.bak") if (-e $met_file);
                my $meteor_scores_ref = read_metric_scores('METEOR', $met_file, \%candCntHsh);
                METEOR_Sent($stem, $prev_new_cands_file, $met_file, $meteor_scores_ref);
                print "Finished getting METEOR stats ...\n";
            }
            if (($is_multi_obj && $metric =~ /ribes/i) || $metric eq "RIBES") {
                $met_file = "$out_dir/ribes.out.ribes";
                safesystem("cp $met_file ${met_file}.bak") if (-e $met_file);
                my $ribes_scores_ref = read_metric_scores('RIBES', $met_file, \%candCntHsh);
                RIBES_Sent($stem, $prev_new_cands_file, $met_file, $out_dir, $ribes_scores_ref);
                print "Finished getting RIBES stats ...\n";
            }
            for my $curr_metric ( split(/:/, $metric) ) {
                if (($is_multi_obj && $curr_metric =~ /bleu(\d)/i) || $metric =~ /^BLEU(\d)$/) {
                    my $max_ngram = $1;
                    $met_file = "$out_dir/bleu${max_ngram}.out.bleu${max_ngram}";
                    safesystem("cp $met_file ${met_file}.bak") if (-e $met_file);
                    my $bleu_scores_ref = read_metric_scores('BLEU${max_ngram}', $met_file, \%candCntHsh);
                    BLEU_Sent($stem, $prev_new_cands_file, $met_file, $bleu_scores_ref, $max_ngram);
                    print "Finished getting BLEU${max_ngram} stats ...\n";
                }
                if (($is_multi_obj && $curr_metric =~ /bleu(?!\d)/i) || $metric eq "BLEU") {
                    $met_file = "$out_dir/bleu.out.bleu";
                    safesystem("cp $met_file ${met_file}.bak") if (-e $met_file);
                    my $bleu_scores_ref = read_metric_scores('BLEU', $met_file, \%candCntHsh);
                    BLEU_Sent($stem, $prev_new_cands_file, $met_file, $bleu_scores_ref, 4);
                    print "Finished getting BLEU stats ...\n";
                }
            }
        }
    }
}
else {
    if (-e $new_cands_file) { ($tot_sents, $new_cands) = countNewCands($nbest_hist, $new_cands_file); }
    else {
        ($tot_sents, $new_cands) = xtract_new_and_merge($nbest_hist, $NBest_file, $new_cands_file);
        xtract_feats($nbest_hist, $feat_hist);
    }
    printf STDERR "Total sentences : $tot_sents\n";
    printf STDERR "Total new candidates added in iteration %2d : %d\n", $run, $new_cands;
}

if ($new_cands > 0) {
    if (($is_multi_obj && $metric =~ /ter/i) || $metric eq "TER") {
        $met_file = "$out_dir/ter.out.ter";
        safesystem("cp $met_file ${met_file}.bak") if (-e $met_file);
        my $ter_scores_ref = read_metric_scores('TER', $met_file, \%candCntHsh);
        TER_Sent($run, $stem, $new_cands_file, $met_file, $out_dir, $ter_scores_ref);
        $scores_file = "$out_dir/ter.scores.ter";
        xtract_scores("TER", $met_file, $scores_file);
        print "Finished getting TER stats ...\n";
    }
    if (($is_multi_obj && $metric =~ /meteor/i) || $metric eq "METEOR") {
        $met_file = "$out_dir/meteor.out.meteor";
        safesystem("cp $met_file ${met_file}.bak") if (-e $met_file);
        my $meteor_scores_ref = read_metric_scores('METEOR', $met_file, \%candCntHsh);
        METEOR_Sent($stem, $new_cands_file, $met_file, $meteor_scores_ref);
        print "Finished getting METEOR stats ...\n";
    }
    if (($is_multi_obj && $metric =~ /ribes/i) || $metric eq "RIBES") {
        $met_file = "$out_dir/ribes.out.ribes";
        safesystem("cp $met_file ${met_file}.bak") if (-e $met_file);
        my $ribes_scores_ref = read_metric_scores('RIBES', $met_file, \%candCntHsh);
        RIBES_Sent($stem, $new_cands_file, $met_file, $out_dir, $ribes_scores_ref);
        $scores_file = "$out_dir/ribes.scores.ribes";
        xtract_scores("RIBES", $met_file, $scores_file);
        print "Finished getting RIBES stats ...\n";
    }
    for my $curr_metric ( split(/:/, $metric) ) {
        if (($is_multi_obj && $curr_metric =~ /bleu(\d)/i) || $metric =~ /^BLEU(\d)$/) {
            my $max_ngram = $1;
            $met_file = "$out_dir/bleu${max_ngram}.out.bleu${max_ngram}";
            safesystem("cp $met_file ${met_file}.bak") if (-e $met_file);
            my $bleu_scores_ref = read_metric_scores('BLEU${max_ngram}', $met_file, \%candCntHsh);
            BLEU_Sent($stem, $new_cands_file, $met_file, $bleu_scores_ref, $max_ngram);
            print "Finished getting BLEU${max_ngram} stats ...\n";
        }
        if (($is_multi_obj && $curr_metric =~ /bleu(?!\d)/i) || $metric eq "BLEU") {
            $met_file = "$out_dir/bleu.out.bleu";
            safesystem("cp $met_file ${met_file}.bak") if (-e $met_file);
            my $bleu_scores_ref = read_metric_scores('BLEU', $met_file, \%candCntHsh);
            BLEU_Sent($stem, $new_cands_file, $met_file, $bleu_scores_ref, 4);
            print "Finished getting BLEU stats ...\n";
        }
    }
}
if ($is_multi_obj) {
    if (-e $pareto_clsfr) { safesystem("rm -f $pareto_clsfr"); }

    #$cmd = "$ENV{PY_HOME}/bin/python $pareto_scrpt --nbest $nbest_hist --out $pareto_out";
    $cmd = "/home/msiahban/Modules/PYTHON/2.6.2/bin/python $pareto_scrpt --nbest $nbest_hist --out $pareto_out";
    $cmd .= " --cls $pareto_clsfr --comb-wgts $comb_wgts" if ($multi_obj_style eq "pareto" || $multi_obj_style =~ /^ensemble/);
    for my $curr_metric ( split(/:/, $metric) ) {
        if ($curr_metric =~ /bleu(\d)/i) { $cmd .= " --acc $out_dir/bleu$1.out.bleu$1"; }
        $cmd .= " --acc $out_dir/bleu.out.bleu" if ($curr_metric =~ /bleu(?!\d)/i);
        $cmd .= " --acc $out_dir/meteor.out.meteor" if ($curr_metric =~ /meteor/i);
        $cmd .= " --acc $out_dir/ribes.scores.ribes" if ($curr_metric =~ /ribes/i);
        $cmd .= " --err $out_dir/ter.scores.ter" if ($curr_metric =~ /ter/i);
    }
    safesystem("$cmd >> pareto.log");

    if ($multi_obj_style eq "linear-comb") {
        #$cmd = "$ENV{PY_HOME}/bin/python $lin_comb_scrpt --out $lin_comb_out --comb-wgts $comb_wgts";
        $cmd = "/home/msiahban/Modules/PYTHON/2.6.2/bin/python $lin_comb_scrpt --out $lin_comb_out --comb-wgts $comb_wgts";
        for my $curr_metric ( split(/:/, $metric) ) {
            if ($curr_metric =~ /bleu(\d)/i) { $cmd .= " --acc $out_dir/bleu$1.out.bleu$1"; }
            $cmd .= " --acc $out_dir/bleu.out.bleu" if ($curr_metric =~ /bleu(?!\d)/i);
            $cmd .= " --acc $out_dir/meteor.out.meteor" if ($curr_metric =~ /meteor/i);
            $cmd .= " --acc $out_dir/ribes.scores.ribes" if ($curr_metric =~ /ribes/i);
            $cmd .= " --err $out_dir/ter.scores.ter" if ($curr_metric =~ /ter/i);
        }
        safesystem("$cmd");
    }
}
#safesystem("$collate_scrpt $run $work_dir");

# This routine counts the new candidates from the aggregated nbest list and new candidates file ##
## This is especially helpful to resume the crashed extraction job ##
sub countNewCands {
    my $nbest_hist = shift;
    my $new_cands_file = shift;

    my $sent_id;
    my $tot_sents = 0;
    my $new_cands = 0;
    my $prev_sent_id = -1;
    %candCntHsh = ();

    open(PNB, "<:encoding(utf8)", $nbest_hist);
    while(<PNB>) {
        chomp;
        /^(\d+)\s*\|/;
        $sent_id = $1;
        $candCntHsh{$sent_id}++;
        if ($sent_id != $prev_sent_id) {
            $tot_sents++;
            $prev_sent_id = $sent_id;
        }
    }
    close(PNB);

    open(CNB, "<:encoding(utf8)", $new_cands_file);
    while(<CNB>) {
        chomp;
        /^(\d+)\s*\|/;
        $sent_id = $1;
        $new_cands++;
        $candCntHsh{$sent_id}--;
    }
    close(CNB);

    return ($tot_sents, $new_cands);
}

sub xtract_new_and_merge {
    my $nbest_hist = shift;
    my $curr_nbfile = shift;
    my $new_cands_file = shift;

    my $cand;
    my $line;
    my $sent_id;
    my $tot_sents = 0;
    my $feat_str;
    my $cand_feat;
    my $curr_scr;
    my $new_cands = 0;
    my $cand_counter = 0;
    my %nBestHsh = ();
    my %currNBestHoH = ();
    %candCntHsh = ();

    print "Reading n-best file : $curr_nbfile ...\n";
    open(CNB, "<:encoding(utf8)", $curr_nbfile);
    while(<CNB>) {
        chomp;
        ($sent_id, $cand, $feat_str, $curr_scr) = split(/\s*\|\|\|\s/);
        $cand =~ s/^\s+|\s+$//g;
        $cand_feat = $cand . " ||| " . $feat_str;
        if (!exists $currNBestHoH{$sent_id}) {
            %{ $currNBestHoH{$sent_id} } = ();
            $cand_counter = 0;
            $tot_sents++;
        }

        $cand_counter++;
        $currNBestHoH{$sent_id}{$cand_feat} = $cand_counter . " ### " . $_;
    }
    close(CNB);

    if (-e $nbest_hist) {
        open(PNB, "<:encoding(utf8)", $nbest_hist);
        while(<PNB>) {
            chomp;
            ($sent_id, $cand, $feat_str, $curr_scr) = split(/\s*\|\|\|\s/);
            $cand =~ s/^\s+|\s+$//g;
            $cand_feat = $cand . " ||| " . $feat_str;
            $candCntHsh{$sent_id}++;
            push @{ $nBestHsh{$sent_id} }, $_;
            if (!$retain_all_hyp && exists $currNBestHoH{$sent_id}{$cand_feat}) {
                delete $currNBestHoH{$sent_id}{$cand_feat};
            }
        }
        close(PNB);
    }

    # Now write the new candidates (that were not found in earlier iterations) in the temporary file
    open(PNB, ">:utf8", $nbest_hist);
    open(TF, ">:utf8", $new_cands_file);
    #for $sent_id (sort {$a <=> $b} keys %currNBestHoH) {
    for ($sent_id = 0; $sent_id < $tot_sents; $sent_id++) {

        foreach $line (@{ $nBestHsh{$sent_id} }) {
            print PNB "$line\n";
        }

        for $cand_feat (sort {&getField1($currNBestHoH{$sent_id}{$a}) <=> &getField1($currNBestHoH{$sent_id}{$b})} keys %{ $currNBestHoH{$sent_id} }) {
            $new_cands++;
            ($cand_counter, $line) = split(/ ### /, $currNBestHoH{$sent_id}{$cand_feat});
            print TF "$line\n";
            print PNB "$line\n";
        }
    }
    close(TF);
    close(PNB);

    return ($tot_sents, $new_cands);
}

sub getField1 {
    my $entry = shift;
    my ($c_cnt) = split(/ ### /, $entry);
    return $c_cnt;
}

sub xtract_feats {
    my $nbest_hist = shift;
    my $feat_hist = shift;

    my $prev_sent_id = -1;
    my $tot_feats = 0;
    my $feat_name_str = "";
    my $tot_cands = 0;
    my $cand_feat;
    my @candFeatArr = ();

    print STDERR "\nCollecting feature stats from N-best file ...\n";
    open(HYP, "<:encoding(utf8)", $nbest_hist) or die "Can't read $nbest_hist\n";
    open(FEAT, ">:utf8", $feat_hist) or die "Can't open $feat_hist for writing\n";
    while(<HYP>) {
        chomp;
        my ($sent_id, $cand_hyp, $feat_str, $model_scr) = split(/\s*\|\|\|\s/);
        if ($. == 1) { ($tot_feats, $feat_name_str) = peek_to_get_features($feat_str); }

        if ($. > 1 && $prev_sent_id != $sent_id) {
            print FEAT "FEATURES_TXT_BEGIN_0 $prev_sent_id $tot_cands $tot_feats $feat_name_str\n";
            foreach $cand_feat (@candFeatArr) { print FEAT "$cand_feat\n"; }
            print FEAT "FEATURES_TXT_END_0\n";
            $tot_cands = 0;
            undef @candFeatArr;
        }

        $cand_feat = get_features($feat_str);
        push @candFeatArr, $cand_feat;
        $tot_cands++;
        $prev_sent_id = $sent_id;
    }
    # Write the feats for the candidates of the last sentence
    print FEAT "FEATURES_TXT_BEGIN_0 $prev_sent_id $tot_cands $tot_feats $feat_name_str\n";
    foreach $cand_feat (@candFeatArr) { print FEAT "$cand_feat\n"; }
    print FEAT "FEATURES_TXT_END_0\n";

    close(HYP);
    close(FEAT);
}

sub peek_to_get_features {
    my $feat_str = shift;
    my $label;
    my $tot_feats = 0;
    my @order = ();
    my @tempArr = ();

    foreach my $tok (split /\s+/, $feat_str) {
        if ($tok =~ /^([a-z][0-9a-z]*):/i) {
            $label = $1;
        } elsif ($tok =~ /^-?[-0-9.e]+$/) {
            # a score found, remember it
            die "Found a score but no label before it! Bad nbestlist '$NBest_file'!" if !defined $label;
            $tot_feats++;
            push @order, $label;
        } else {
            die "Not a label, not a score '$tok'. Failed to parse the scores string: '$feat_str' of nbestlist '$NBest_file'";
        }
    }

    my $feat_cnt = -1;
    for (my $i = 0; $i < scalar(@order); $i++) {
        if ($i > 0 && $order[$i] ne $order[$i-1]) { $feat_cnt = 0; }
        else { $feat_cnt++; }
        push @tempArr, "${order[$i]}_${feat_cnt}";
    }

    return ($tot_feats, join(' ', @tempArr));
}


sub get_features {
    my $feat_str = shift;
    my $label;
    my @retArr = ();

    foreach my $tok (split /\s+/, $feat_str) {
        if ($tok =~ /^([a-z][0-9a-z]*):/i) {
            $label = $1;
        } elsif ($tok =~ /^-?[-0-9.e]+$/) {
            # a score found, remember it
            die "Found a score but no label before it! Bad nbestlist '$NBest_file'!" if (!defined $label);
            push @retArr, $tok;
        } else {
            die "Not a label, not a score '$tok'. Failed to parse the scores string: '$feat_str' of nbestlist '$NBest_file'";
        }
    }

    return join(' ', @retArr);
}

sub xtract_scores {
    my ($metric, $met_file, $scores_file) = @_;
    my @entries = ();

    open(MF, $met_file);
    open(SF, ">$scores_file");
    while(<MF>) {
        chomp;
        next if $_ =~ /^(Hypothesis|Reference) File/;
        @entries = split(/\s+/);
        if ($metric =~ /ter/i) { print SF "$entries[-1]\n"; }
        elsif ($metric =~ /ribes/i) { print SF "$entries[0]\n"; }
    }
    close(MF);
    close(SF);
}

sub TER_Sent {
    my ($run, $stem, $NBest_file, $met_file, $out_dir, $oldScoresRef) = @_;

    print STDERR "\nCollecting sufficient stats for TER from N-best file ...\n";
    $cmd = "$ter_parallel_cmd -run=$run -ref-stem=$stem -nbest-file=$NBest_file -metric-dir=$out_dir";
    safesystem($cmd);

    my @terArr = ();
    open(MF, $met_file);
    while(<MF>) {
        chomp;
        next if $_ =~ /^(Hypothesis|Reference) File/;
        push @terArr, $_;
    }
    close(MF);

    open (HYP, "<:encoding(utf8)", $NBest_file) or die "Can't read $NBest_file";
    my $s = 0;
    my $prev_refNum = -1;
    my @TER = ();
    while (<HYP>){
        chomp;
        my @PARTS=split(/\s*\|\|\|\s/,$_);
        my $refNum = $PARTS[0];
        if ($refNum != $prev_refNum) { $s = 0; }
        $TER[$refNum][$s] = shift @terArr;
        $prev_refNum = $refNum;
        $s++;
    }
    close(HYP);

    print "Calling merge_metric_scores() for merging Metric scores ...\n";
    merge_metric_scores('TER', $met_file, $oldScoresRef, \@TER);
    print "Returning from TER_Sent routine ...\n";
}

sub METEOR_Sent {
    my ($stem, $NBest_file, $met_file, $oldScoresRef) = @_;

    print STDERR "\nCollecting sufficient stats for METEOR from N-best file ...\n";
    $cmd = "$meteor_parallel_cmd -run=$run -ref-stem=$stem -nbest-file=$NBest_file -metric-dir=$out_dir";
    safesystem($cmd);

    my @meteorArr = ();
    open(MF, $met_file) or die "Can't read $met_file";
    while(<MF>) {
        chomp;
        push @meteorArr, $_;
    }
    close(MF);

    open (HYP, "<:encoding(utf8)", $NBest_file) or die "Can't read $NBest_file";
    my $s = 0;
    my @METEOR = ();
    my $prev_refNum = -1;
    while (<HYP>){
        chomp;
        my @PARTS=split(/\s*\|\|\|\s/,$_);
        my $refNum = $PARTS[0];
        if ($refNum != $prev_refNum) { $s = 0; }
        $METEOR[$refNum][$s] = shift @meteorArr;
        $prev_refNum = $refNum;
        $s++;
    }
    close(HYP);

    print "Calling merge_metric_scores() for merging Metric scores ...\n";
    merge_metric_scores('METEOR', $met_file, $oldScoresRef, \@METEOR);
    print "Returning from METEOR_Sent routine ...\n";
}

sub RIBES_Sent {
    my ($stem, $NBest_file, $met_file, $out_dir, $oldScoresRef) = @_;

    print STDERR "\nCollecting sufficient stats for RIBES from N-best file ...\n";
    $cmd = "perl $sent_ribes_scrpt $stem $NBest_file $out_dir";
    safesystem($cmd);

    my @ribesArr = ();
    open(MF, $met_file) or die "Can't read $met_file";
    while(<MF>) {
        chomp;
        push @ribesArr, $_ if ($_ =~ /sentence\s+\d+$/);
    }
    close(MF);

    open (HYP, "<:encoding(utf8)", $NBest_file) or die "Can't read $NBest_file";
    my $s = 0;
    my @RIBES = ();
    my $prev_refNum = -1;
    while (<HYP>){
        chomp;
        my @PARTS=split(/\s*\|\|\|\s/,$_);
        my $refNum = $PARTS[0];
        if ($refNum != $prev_refNum) { $s = 0; }
        $RIBES[$refNum][$s] = shift @ribesArr;
        $prev_refNum = $refNum;
        $s++;
    }
    close(HYP);

    print "Calling merge_metric_scores() for merging Metric scores ...\n";
    merge_metric_scores('RIBES', $met_file, $oldScoresRef, \@RIBES);
    print "Returning from RIBES_Sent routine ...\n";
}

sub BLEU_Sent {
    my ($stem, $NBest_file, $met_file, $oldScoresRef, $max_ngram) = @_;

    print STDERR "\nCollecting sufficient stats for BLEU from N-best file ...\n";
    $cmd = "perl $sent_bleu_scrpt $stem $NBest_file $met_file $max_ngram";
    safesystem($cmd);

    my @bleuArr = ();
    open(MF, $met_file) or die "Can't read $met_file";
    while(<MF>) {
        chomp;
        push @bleuArr, $_;
    }
    close(MF);

    open (HYP, "<:encoding(utf8)", $NBest_file) or die "Can't read $NBest_file";
    my $s = 0;
    my @BLEU = ();
    my $prev_refNum = -1;
    while (<HYP>){
        chomp;
        my @PARTS=split(/\s*\|\|\|\s/,$_);
        my $refNum = $PARTS[0];
        if ($refNum != $prev_refNum) { $s = 0; }
        $BLEU[$refNum][$s] = shift @bleuArr;
        $prev_refNum = $refNum;
        $s++;
    }
    close(HYP);

    print "Calling merge_metric_scores() for merging Metric scores ...\n";
    merge_metric_scores('BLEU', $met_file, $oldScoresRef, \@BLEU);
    print "Returning from BLEU_Sent routine ...\n";
}

sub merge_metric_scores {
    my $met = shift;
    my $met_file = shift;
    my $oldScoresRef = shift;
    my $newScoresRef = shift;
    my $refNum;
    my $scr;
    my @lines = ();

    print "Entering merge_metric_scores() routine ...\n";
    if ($met =~ /ter/i && -e $met_file) {
        open(IN, "$met_file") or die "Can't open $met_file: $!";
        for (my $i=0; $i<2; $i++) {
            $_ = <IN>;
            chomp();
            push @lines, $_;
        }
        close(IN);
    }

    my @oldScoresArr = @$oldScoresRef;
    my @newScoresArr = @$newScoresRef;
    open(OUT, ">", "$met_file") or die "Can't open $met_file: $!";
    if ($met =~ /ter/i) {
        foreach (@lines) { print OUT "$_\n"; }
    }

    my $s = 0;
    my $tot_item = scalar(@newScoresArr) > scalar(@oldScoresArr) ? scalar(@newScoresArr) : scalar(@oldScoresArr);
    die "Total # of items ($tot_item) doesn't match the # of sentences ($tot_sents). Exiting!!\n" if($tot_item != $tot_sents);
    for ($refNum=0; $refNum<$tot_item; $refNum++) {
        if ( scalar(@oldScoresArr) > 0 ) {
            foreach $scr ( @{ $oldScoresArr[$refNum] } ) {
                if ($met =~ /ter|ribes/i) {
                    $scr =~ s/^($set_id\.)\d+(:1)\s/$1$s$2 / if ($met =~ /ter/i);
                    $scr =~ s/( sentence)\s+\d+$/$1 $s/ if ($met =~ /ribes/i);
                    $s++;
                }
                print OUT "$scr\n";
            }
        }
        foreach $scr ( @{ $newScoresArr[$refNum] } ) {
            if ($met =~ /ter|ribes/i) {
                $scr =~ s/^($set_id\.)\d+(:1)\s/$1$s$2 / if ($met =~ /ter/i);
                $scr =~ s/( sentence)\s+\d+$/$1 $s/ if ($met =~ /ribes/i);
                $s++;
            }
            if ($round_scores) {
                if ($met =~ /ter/i) { $scr =~ s/([0-9\.]+)$/my $r_scr=nearest(0.001, $1);$r_scr/e; }
                elsif ($met =~ /ribes/i) { $scr =~ s/^([0-9\.]+)/my $r_scr=nearest(0.001, $1);$r_scr/e; }
                else { $scr = nearest(0.001, $scr); }
            }
            print OUT "$scr\n";
        }
    }
    close(OUT);
    print "Returning from merge_metric_scores() routine ...\n";
}

sub read_metric_scores {
    my $met = shift;
    my $met_file = shift;
    my $nb_cnt_hsh_ref = shift;
    my $refNum;
    my $cand_count;
    my @metScoresArr = ();

    if (!-e $met_file) { return \@metScoresArr; }

    open(IN, $met_file) or die "Can't open $met_file: $!";
    my @lines = <IN>;
    chomp(@lines);
    if ($met =~ /ter/i) { shift(@lines); shift(@lines); }
    if ($met =~ /ribes/i && $lines[-1] !~ / sentence\s+\d+$/) { pop(@lines); }

    my %candCntHsh = %$nb_cnt_hsh_ref;
    for $refNum (sort {$a <=> $b} keys %candCntHsh) {
        $cand_count = 0;
        while ($cand_count < $candCntHsh{$refNum}) {
            $metScoresArr[$refNum][$cand_count] = shift(@lines);
            $cand_count++;
        }
    }
    close(IN);
    return \@metScoresArr;
}

sub safesystem {
    print STDERR "Executing: @_\n";
    system(@_);
    if ($? != 0) { die "Failed executing [@_]\n"; }

    if ($? == -1) {
        print STDERR "Failed to execute: @_\n  $!\n";
        exit(1);
    }
    elsif ($? & 127) {
        printf STDERR "Execution of: @_\n  died with signal %d, %s coredump\n",
        ($? & 127),  ($? & 128) ? 'with' : 'without';
        exit 1;
    }
    else {
        my $exitcode = $? >> 8;
        print STDERR "Exit code: $exitcode\n" if $exitcode;
        return ! $exitcode;
    }
}

