#!/usr/bin/perl

use Cwd 'abs_path';
use File::Basename;
use lib dirname(abs_path($0));

use TrainConfig;
use strict;

my $config_file = $ARGV[0];

if (!defined $config_file) { die "usage: $0 <Training config file>\nSpecify a training config file. Exiting!\n"; }
if (!-e $config_file) { die "Training config file $config_file does not exist. Exiting!\n"; }

&check_modules();
my $cfg = TrainConfig->new($config_file);
print "INFO: Model output dir : $cfg->{KRIYA_MODELS}\n";
print "INFO: Source language  : $cfg->{src}\n";
print "INFO: Target language  : $cfg->{tgt}\n";
print "INFO: Sets to process  : $cfg->{STEPS}\n";

my $step_lc_dir;
my $phr_align_dir;
my $comb_pre = "all.$cfg->{src}-$cfg->{tgt}";

# Create the directory for writing the outputs of the Moses training steps
if (defined $cfg->{TRAIN_DIR}) {
    $phr_align_dir = "$cfg->{KRIYA_MODELS}/training/phr-alignments";
    if (-e "$phr_align_dir") { die "ERROR: Moses training directory $phr_align_dir already exists. Exiting!\n"; }
    safeSystem("mkdir -p $phr_align_dir");
}

# Pre-process the corpus for each Dev|Test|Train sets
foreach my $step ( split(/,/, $cfg->{STEPS}) ) {
    print STDERR "\nRunning pre-processing steps on $step set ...\n";

    # Create the directory for writing the outputs of the pre-processing steps
    $step_lc_dir = "LC_${step}_DIR";
    if (-e $cfg->{$step_lc_dir}) { die "ERROR: Pre-process output directory $cfg->{$step_lc_dir} already exists. Exiting!\n"; }
    safeSystem("mkdir -p $cfg->{$step_lc_dir}");

    &run_preprocess( $step );
}

# Run Moses training pipeline for the Train set
if (defined $cfg->{TRAIN_DIR}) {
    print STDERR "\nRunning Moses training steps on TRAIN set ...\n";
    $step_lc_dir = "LC_TRAIN_DIR";
    &run_moses_train($step_lc_dir, $phr_align_dir);
}

sub check_modules {
    if (!defined $ENV{'GIZA_DIR'} || !defined $ENV{'MOSES_DIR'} || !defined $ENV{'SCRIPTS_ROOTDIR'}) {
        print STDERR "ERROR: Three env variables, GIZA_DIR, MOSES_DIR, SCRIPTS_ROOTDIR must be set. One or more of them are undefined.\n";
        print STDERR "\tPlease load Giza and Moses/SVN_20101028 modules before launching $0. Exiting!\n";
        exit(1);
    }
    else {
        print STDERR "INFO: Env variable GIZA_DIR       : $ENV{'GIZA_DIR'}\n";
        print STDERR "INFO: Env variable MOSES_DIR      : $ENV{'MOSES_DIR'}\n";
        print STDERR "INFO: Env variable SCRIPTS_ROOTDIR: $ENV{'SCRIPTS_ROOTDIR'}\n";
    }
}

sub run_preprocess {
    my $step = shift;

    my $cmd;
    my $step_dir;
    my $step_lc_dir;
    my $step_pre = "${step}_PRE";
    my @pres = ();

    for my $pre ( split(/,/, $cfg->{$step_pre}) ) {
        $step_dir = "${step}_DIR";
        $step_lc_dir = "LC_${step}_DIR";

        # Step-0: Cleaning the corpus file
        my $new_pre = &pp_clean_corpus($step_dir, $step_lc_dir, $pre);
        if ($pre ne $new_pre) { $step_dir = $step_lc_dir; }

        # Steps-1 & 2: Lower-case and tokenize the corpus files
        my $src_pre = &pp_lc_nd_tok($step_dir, $step_lc_dir, $pre, $new_pre, "src");
        my $tgt_pre = &pp_lc_nd_tok($step_dir, $step_lc_dir, $pre, $new_pre, "tgt");

        # Concatenate multiple files into single file
        $cmd = "cat $cfg->{$step_lc_dir}/$src_pre.$cfg->{src} >> $cfg->{$step_lc_dir}/$comb_pre.$cfg->{src}";
        safeSystem($cmd);
        $cmd = "cat $cfg->{$step_lc_dir}/$tgt_pre.$cfg->{tgt} >> $cfg->{$step_lc_dir}/$comb_pre.$cfg->{tgt}";
        safeSystem($cmd);
    }
}

sub pp_clean_corpus {
    my $step_dir = shift;
    my $step_lc_dir = shift;
    my $pre = shift;

    if ( $cfg->{clean} !~ /true/i ) { return $pre; }

    print "    ** Cleaning corpus turned on ...\n";
    my $py_scrpt = "$cfg->{KRIYA_PXTR}/pre-process/clean_corpus.py"; 
    my $cmd = "/usr/bin/python $py_scrpt $cfg->{$step_dir} $cfg->{$step_lc_dir} $pre $cfg->{src} $cfg->{tgt} $cfg->{max_sent_len}";
    safeSystem($cmd);
    return "$pre.cln";
}

sub pp_lc_nd_tok {
    my $step_dir = shift;
    my $step_lc_dir = shift;
    my $pre = shift;
    my $new_pre = shift;
    my $src_or_tgt = shift;

    my $pl_scrpt;
    my $cmd;
    my $what_pp = "${src_or_tgt}_pp";
    my $lc_in_dir = $cfg->{$step_dir};

    # Tokenize if the {src|tgt}_pp param specifies so
    if ($cfg->{$what_pp} =~ /tok/) {
        print "    ** $cfg->{$src_or_tgt} : Tokenization turned on ...\n";
        $pl_scrpt = "$ENV{'SCRIPTS_ROOTDIR'}/tokenizer/tokenizer.perl";
        $cmd = "perl $pl_scrpt -l $cfg->{$src_or_tgt} < $cfg->{$step_dir}/$new_pre.$cfg->{$src_or_tgt} > $cfg->{$step_lc_dir}/$pre.tok.$cfg->{$src_or_tgt}";
        safeSystem($cmd);
        $lc_in_dir = $cfg->{$step_lc_dir};
        $new_pre = "$pre.tok";
    }

    # Lower-case if the {src|tgt}_pp param specifies so
    if ($cfg->{$what_pp} =~ /lc/) {
        print "    ** $cfg->{$src_or_tgt} : Lower-casing turned on ...\n";
        $pl_scrpt = "$ENV{'SCRIPTS_ROOTDIR'}/tokenizer/lowercase.perl";
        $cmd = "perl $pl_scrpt < $lc_in_dir/$new_pre.$cfg->{$src_or_tgt} > $cfg->{$step_lc_dir}/$new_pre.lc.$cfg->{$src_or_tgt}";
        safeSystem($cmd);
        $new_pre = "$new_pre.lc";
    }

    return $new_pre;
}

sub run_moses_train {
    my $step_lc_dir = shift;
    my $phr_align_dir = shift;

    my $tr_scrpt = "$ENV{'SCRIPTS_ROOTDIR'}/training/train-model.perl";
    my $cmd = "perl $tr_scrpt --first-step $cfg->{first_step} --last-step $cfg->{last_step} --parallel --parts $cfg->{giza_parts} --scripts-root-dir $ENV{'SCRIPTS_ROOTDIR'} --bin-dir $ENV{'GIZA_DIR'} --root-dir $phr_align_dir --corpus $cfg->{$step_lc_dir}/$comb_pre -f $cfg->{src} -e $cfg->{tgt} --max-phrase-length=$cfg->{max_phr_len} -alignment grow-diag-final-and --factor-delimiter='|||' >& $cfg->{KRIYA_MODELS}/training/training.log";
    print "  ** Executing : $cmd\n";
    safeSystem($cmd);
}

sub safeSystem {
    #print "  ** Executing : @_\n";
    system(@_);

    if ($? == -1) {
        print STDERR "Failed to execute: @_\n  $!\n";
        exit 1;
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
}1;

