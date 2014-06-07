#!/usr/bin/perl -w

use Math::Round;

use strict;
use Cwd 'abs_path';
use File::Basename;
use Getopt::Long;

my $stem = undef;
my $nbest_file = undef;
my $work_dir = undef;
my $max_ngram = 4;
my $set_id = "MetPlotTest";
my $round_scores = 1;
my $cmd;
my $usage = 0;

my $metric = undef;
my $multi_obj_style = undef;
my $comb_wgts = undef;

GetOptions(
    "refs=s" => \$stem,
    "nbest-file=s" => \$nbest_file,
    "work-dir=s" => \$work_dir,
    "set-id=s" => \$set_id,
    "metric=s" => \$metric,
    "max-ngram=i" => \$max_ngram,
    "multi-obj-style=s" => \$multi_obj_style,
    "comb-wgts=s" => \$comb_wgts,
    "help" => \$usage
) or exit(1);

if ($usage || !defined $stem || !defined $nbest_file || !defined $work_dir) {
    print STDERR "Usage: ".basename($0)." --refs=<references> --set-id=<set-id> --work-dir=<MERT Working dir>
Options:
  --refs=STRING ... set of comma separated reference files
  --nbest-file=STRING ... nbest-file
  --work-dir=mert-dir ... where to find the N-best files
  --set-id=STRING ... unique set id indicating where the tuning/ test set sentences come from; for TER (default MetPlotTest)
  --metric=STRING ... what metric to use (BLEU, RIBES and TER are supported presently)
  --multi-obj-style=STRING ... Multi-objective tuning style (multi-obj must be true)
  --comb-wgts ... combination weights (colon separated) for the linear combination and pareto style multi-objective
  --help ... prints this message
\n";
exit(1);
}

if(!defined $ENV{TER_DIR}) { die "**ERROR: Needs the Environmental variable TER_DIR to be defined. Exiting!!\n"; }
$work_dir =~ s/\/$//;
$work_dir = abs_path($work_dir);

my $meteor_parallel_cmd = abs_path(dirname($0))."/sentence-METEOR.pl";
my $ter_parallel_cmd = abs_path(dirname($0))."/sentence-TER.pl";
my $sent_bleu_scrpt = abs_path(dirname($0))."/multi-sent-bleu.perl";
my $sent_ribes_scrpt = abs_path(dirname($0))."/multi-sent-ribes.perl";

my $stats_dir = "${work_dir}/Metric-Plots-Stats";
safesystem("mkdir $stats_dir") if !-e $stats_dir;

my $bleu_scores_file = "${stats_dir}/bleu.out.bleu";
my $meteor_scores_file = "${stats_dir}/meteor.out.meteor";
my $ribes_scores_file = "${stats_dir}/ribes.out.ribes";
my $ter_scores_file = "${stats_dir}/ter.out.ter";
my $out_file = "${stats_dir}/1K.scores.dat";

my $tot_nbest_cands = 0;
my $retain_all_hyp = 0;
my $tot_sents = 0;
my @metricsArr = ();
my @featWgts = ();
my %candCntHsh = ();
my %modelScoresHoH = ();
my %metricScoresHoH = ();

load_model_scores($nbest_file);

BLEU_Sent($stem, $nbest_file, $bleu_scores_file, $max_ngram);
METEOR_Sent($stem, $nbest_file, $meteor_scores_file, $stats_dir);
RIBES_Sent($stem, $nbest_file, $ribes_scores_file, $stats_dir);
TER_Sent($stem, $nbest_file, $ter_scores_file, $stats_dir);

read_metric_scores("BLEU", $bleu_scores_file);
read_metric_scores("METEOR", $meteor_scores_file);
read_metric_scores("RIBES", $ribes_scores_file);
read_metric_scores("TER", $ter_scores_file);
write_score_stats();


sub load_model_scores {
    my $nbest_hist = shift;
    %candCntHsh = ();

    my $cand_id = 0;
    my $prev_sent_id = -1;
    my $new_model_scr;
    my ($sent_id, $cand, $feat_str, $model_scr);

    print "Loading model scores from file $nbest_hist ...\n\n";
    open(PNB, "<:encoding(utf8)", $nbest_hist);
    while(<PNB>) {
        chomp;
        ($sent_id, $cand, $feat_str, $model_scr) = split(/\s*\|\|\|\s/);
        if ($sent_id != $prev_sent_id) {
            $cand_id = 0;
            $tot_sents++;
            $prev_sent_id = $sent_id;
        }

        $modelScoresHoH{$sent_id}{$cand_id++} = $model_scr;
        $candCntHsh{$sent_id}++;
    }
    close(PNB);
}

sub read_metric_scores {
    my $met = shift;
    my $met_file = shift;
    my $line;
    my $sent_id;
    my $cand_count;

    print "Loading $met scores from file $met_file ...\n";
    push @metricsArr, $met;
    open(IN, $met_file) or die "Can't open $met_file: $!";
    my @lines = <IN>;
    chomp(@lines);
    close(IN);

    if ($met =~ /ter/i) { shift(@lines); shift(@lines); }
    if ($met =~ /ribes/i && $lines[-1] !~ / sentence\s+\d+$/) { pop(@lines); }

    for $sent_id (sort {$a <=> $b} keys %candCntHsh) {
        $cand_count = 0;
        while ($cand_count < $candCntHsh{$sent_id}) {
            $line = shift(@lines);
            if ($met =~ /ter/i) { $line = (split /\s+/, $line)[-1]; }
            elsif ($met =~ /ribes/i) { $line = (split /\s+/, $line)[0]; }
            push @{$metricScoresHoH{$sent_id}{$cand_count++}}, $line;
        }
    }
}

sub TER_Sent {
    my ($stem, $NBest_file, $met_file, $out_dir) = @_;

    print STDERR "\nCollecting sufficient stats for TER from N-best file ...\n";
    $cmd = "$ter_parallel_cmd -run=0 -ref-stem=$stem -nbest-file=$NBest_file -metric-dir=$out_dir";
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
    my $prev_sent_id = -1;
    my @TER = ();
    while (<HYP>){
        chomp;
        my @PARTS=split(/\s*\|\|\|\s/,$_);
        my $sent_id = $PARTS[0];
        if ($sent_id != $prev_sent_id) { $s = 0; }
        $TER[$sent_id][$s] = shift @terArr;
        $prev_sent_id = $sent_id;
        $s++;
    }
    close(HYP);

    print "Calling merge_metric_scores() for merging Metric scores ...\n";
    merge_metric_scores('TER', $met_file, \@TER);
    print "Returning from TER_Sent routine ...\n";
}

sub METEOR_Sent {
    my ($stem, $NBest_file, $met_file, $out_dir) = @_;

    print STDERR "\nCollecting sufficient stats for METEOR from N-best file ...\n";
    $cmd = "$meteor_parallel_cmd -run=0 -ref-stem=$stem -nbest-file=$NBest_file -metric-dir=$out_dir";
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
    my $prev_sent_id = -1;
    while (<HYP>){
        chomp;
        my @PARTS=split(/\s*\|\|\|\s/,$_);
        my $sent_id = $PARTS[0];
        if ($sent_id != $prev_sent_id) { $s = 0; }
        $METEOR[$sent_id][$s] = shift @meteorArr;
        $prev_sent_id = $sent_id;
        $s++;
    }
    close(HYP);

    print "Calling merge_metric_scores() for merging Metric scores ...\n";
    merge_metric_scores('METEOR', $met_file, \@METEOR);
    print "Returning from METEOR_Sent routine ...\n";
}

sub RIBES_Sent {
    my ($stem, $NBest_file, $met_file, $out_dir) = @_;

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
    my $prev_sent_id = -1;
    while (<HYP>){
        chomp;
        my @PARTS=split(/\s*\|\|\|\s/,$_);
        my $sent_id = $PARTS[0];
        if ($sent_id != $prev_sent_id) { $s = 0; }
        $RIBES[$sent_id][$s] = shift @ribesArr;
        $prev_sent_id = $sent_id;
        $s++;
    }
    close(HYP);

    print "Calling merge_metric_scores() for merging Metric scores ...\n";
    merge_metric_scores('RIBES', $met_file, \@RIBES);
    print "Returning from RIBES_Sent routine ...\n";
}

sub BLEU_Sent {
    my ($stem, $NBest_file, $met_file, $max_ngram) = @_;

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
    my $prev_sent_id = -1;
    while (<HYP>){
        chomp;
        my @PARTS=split(/\s*\|\|\|\s/,$_);
        my $sent_id = $PARTS[0];
        if ($sent_id != $prev_sent_id) { $s = 0; }
        $BLEU[$sent_id][$s] = shift @bleuArr;
        $prev_sent_id = $sent_id;
        $s++;
    }
    close(HYP);

    print "Calling merge_metric_scores() for merging Metric scores ...\n";
    merge_metric_scores('BLEU', $met_file, \@BLEU);
    print "Returning from BLEU_Sent routine ...\n";
}

sub merge_metric_scores {
    my $met = shift;
    my $met_file = shift;
    my $scoresRef = shift;
    my $sent_id;
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

    my @scoresArr = @$scoresRef;
    open(OUT, ">", "$met_file") or die "Can't open $met_file: $!";
    if ($met =~ /ter/i) {
        foreach (@lines) { print OUT "$_\n"; }
    }

    my $s = 0;
    my $tot_item = scalar(@scoresArr);
    die "Total # of items ($tot_item) doesn't match the # of sentences ($tot_sents). Exiting!!\n" if($tot_item != $tot_sents);
    for ($sent_id=0; $sent_id<$tot_item; $sent_id++) {
        foreach $scr ( @{ $scoresArr[$sent_id] } ) {
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

sub write_score_stats {
    my $sent_id;
    my $cand_count;
    my ($s_id, $mod_score, $met_scores);

    open(OUT, ">$out_file") or die "Can't open $out_file for writing: $!";
    my $metrics_list = join("\t", map sprintf("%s", $_), @metricsArr);
    print OUT "#Sent#\tModelScore\t$metrics_list\n";
    for $sent_id (sort {$a <=> $b} keys %candCntHsh) {
        $s_id = sprintf("%4d", $sent_id);
        $cand_count = 0;
        while ($cand_count < $candCntHsh{$sent_id}) {
        #for $cand_count (sort {$candCntHsh{$a} <=> $candCntHsh{$b}} keys %{$candCntHsh{$sent_id}}) {
            $mod_score = sprintf("%g", $modelScoresHoH{$sent_id}{$cand_count});
            $met_scores = join("\t", map sprintf("%g", $_), @{$metricScoresHoH{$sent_id}{$cand_count}});
            print OUT "$s_id\t$mod_score\t$met_scores\n";
            $cand_count++;
        }
    }
    close(OUT);
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

