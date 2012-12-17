#!/usr/bin/perl -w 

# pro-hiero.pl cmpt882 project $
# Usage:
# pro-hiero.pl <foreign> <english> <decoder-executable> <decoder-config>
# For other options see below or run 'mert-moses.pl --help'

# Notes:
# <foreign> and <english> should be raw text files, one sentence per line
# <english> can be a prefix, in which case the files are <english>0, <english>1, etc. are used

# Revision history
# Modified in Mar 2012 for adding stopping criterion based on n-best list additions and fixed number of iterations
# Originally this is modified from the MERT script in Moses, which was modified for Kriya decoder and customized for the HPC cluster @ SFU 
# Apr 2009    Modified by Baskaran Sankaran for use with home-grown (SFU) Hierarchical MT decoder
# Original version by Philipp Koehn

use FindBin qw($Bin);
use File::Basename;

my $minimum_required_change_in_weights = 0.00001;
    # stop if no lambda changes more than this

my $verbose = 0;
my $usage = 0; # request for --help
my $max_runs = 15; # maximum number of PRO iterations
my $___WORKING_DIR = "mert-work";
my $___DEV_F = undef; # required, input text to decode
my $___DEV_E = undef; # required, basename of files with references
my $___GLUE_RULES = undef; # required, file having Glue rules
my $___SCFG_RULES = undef; # required, basename of the directory having the SCFG rule files
my $___DECODER = undef; # required, pathname to the decoder executable
my $___CONFIG = undef; # required, pathname to startup ini file
my $___LM_FILE = undef; # required, LM file (w/ absolute path)
my $___N_BEST_LIST_SIZE = 100;
my $queue_flags = "-l mem=5gb -l walltime=01:30:00";  # extra parameters for parallelizer
      # the -l ws0ssmt is relevant only to JHU workshop
my $___JOBS = undef; # if parallel, number of jobs to use (undef -> serial)
my $___DECODER_PREFIX = ""; # prefix for the decoder
my $___DECODER_FLAGS = ""; # additional parametrs to pass to the decoder (only feature weight related flags)
my $kriya_opts = ""; # parameters for the kriya decoder (non-feature weight options that are directly passed to Kriya)
my $nodes_prop = ""; # specifies the feature name describing the nodes
my $___LAMBDA = undef; # string specifying the seed weights and boundaries of all lambdas
my $continue = 0; # should we try to continue from the last saved step?
my $skip_decoder = 0; # and should we skip the first decoder run (assuming we got interrupted during mert)


# Parameter for effective reference length when computing BLEU score
# This is used by score-nbest-bleu.py
# Default is to use shortest reference
# Use "--average" to use average reference length
# Use "--closest" to use closest reference length
# Only one between --average and --closest can be set
# If both --average is used
#TODO: Pass these through to scorer
my $___AVERAGE = 0;
my $___CLOSEST = 0;

my $allow_unknown_lambdas = 0;
my $allow_skipping_lambdas = 0;

my $pro_opt_metric = "bleu"; # what metric should PRO use?
my $pro_sampler = "threshold"; # defines how the candidates are sampled in PRO
my $mertdir = undef; # path to new mert directory
my $mert_status = 100; # 3 digit code to indicate the status of mert
my $prev_jobid = 0; # id of the previous job aborted (to continue from halfway), default 0
my $qsubwrapper = undef;
my $moses_parallel_cmd = undef;
my $meteor_parallel_cmd = undef;
my $ter_parallel_cmd = undef;
my $old_sge = 0; # assume sge<6.0
my $___CONFIG_BAK = undef; # backup pathname to startup ini file

use strict;
use Getopt::Long;
GetOptions(
  "max-runs=i" => \$max_runs,
  "opt-metric=s" => \$pro_opt_metric, #passed to PRO
  "pro-sampler=s" => \$pro_sampler, #passed to PRO
  "working-dir=s" => \$___WORKING_DIR,
  "input=s" => \$___DEV_F,
  "gluefile=s" => \$___GLUE_RULES,
  "scfgpath=s" => \$___SCFG_RULES,
  "refs=s" => \$___DEV_E,
  "decoder=s" => \$___DECODER,
  "config=s" => \$___CONFIG,
  "lmfile=s" => \$___LM_FILE,
  "nbest=i" => \$___N_BEST_LIST_SIZE,
  "queue-flags=s" => \$queue_flags,
  "nodes-prop=s" => \$nodes_prop,
  "jobs=i" => \$___JOBS,
  "decoder-prefix=s" => \$___DECODER_PREFIX,
  "decoder-flags=s" => \$___DECODER_FLAGS,
  "kriya-opts=s" => \$kriya_opts,
  "lambdas=s" => \$___LAMBDA,
  "continue" => \$continue,
  "skip-decoder" => \$skip_decoder,
  "average" => \$___AVERAGE,
  "closest" => \$___CLOSEST,
  "help" => \$usage,
  "allow-unknown-lambdas" => \$allow_unknown_lambdas,
  "allow-skipping-lambdas" => \$allow_skipping_lambdas,
  "verbose" => \$verbose,
  "mertdir=s" => \$mertdir,
  "mertstatus=i" => \$mert_status,
  "prevjobid=i" => \$prev_jobid,
  "qsubwrapper=s" => \$qsubwrapper, # allow to override the default location
  "mosesparallelcmd=s" => \$moses_parallel_cmd, # allow to override the default location
  "old-sge" => \$old_sge, #passed to moses-parallel
) or exit(1);

# the 4 required parameters can be supplied on the command line directly
# or using the --options
if (scalar @ARGV == 4) {
  # required parameters: input_file references_basename decoder_executable
  $___DEV_F = shift;
  $___DEV_E = shift;
  $___DECODER = shift;
  $___CONFIG = shift;
}

$queue_flags =~ s/__/ /;
print STDERR "After default: $queue_flags\n";

if ($usage || !defined $___DEV_F || !defined $___DEV_E || !defined $___DECODER || !defined $___CONFIG) {
  print STDERR "usage: pro-kriya.pl input-text references decoder-executable decoder.ini
Options:
  --opt-metric=metri-to-optimize ... what metric to optimize (default BLEU)
  --pro-sampler=sampler-to-use ... what sampling method for PRO; supports threshold/ log-sigmoid (default threshold)
  --working-dir=mert-dir ... where all the files are created
  --gluefile=STRING ... file having the Glue rules
  --scfgpath=STRING ... path to the SCFG rule files corresponding to the input sentences files
  --lmfile=STRING ... LM file (w/ absolute path)
  --nbest=100 ... how big nbestlist to generate
  --jobs=N  ... set this to anything to run moses in parallel
  --mosesparallelcmd=STRING ... use a different script instead of moses-parallel
  --queue-flags=STRING  ... anything you with to pass to 
              qsub, eg. '-l ws06osssmt=true'
              The default is 
								-l mem=5gb,walltime=00:50:00
              To reset the parameters, please use \"--queue-flags=' '\" (i.e. a space between
              the quotes).
  --nodes-prop=STRING ... specifies the feature name describing the nodes
  --decoder-prefix=STRING ... prefix for the decoder (such as interpreter to be used)
  --decoder-flags=STRING ... extra parameters for the decoder
  --lambdas=STRING  ... default values and ranges for lambdas, a complex string
         such as 'd:1,0.5-1.5 lm:1,0.5-1.5 tm:0.3,0.25-0.75;0.2,0.25-0.75;0.2,0.25-0.75;0.3,0.25-0.75;0,-0.5-0.5 w:0,-0.5-0.5'
  --allow-unknown-lambdas ... keep going even if someone supplies a new lambda
         in the lambdas option (such as 'superbmodel:1,0-1'); optimize it, too
  --continue  ... continue from the last achieved state
  --skip-decoder ... skip the decoder run for the first time, assuming that
                     we got interrupted during optimization
  --average ... Use either average or shortest (default) reference
                  length as effective reference length
  --closest ... Use either closest or shortest (default) reference
                  length as effective reference length
  --rootdir=STRING  ... where do helpers reside (if not given explicitly)
  --mertdir=STRING ... path to new mert implementation
  --mertstatus=INT ... 3 digit code for the status of MERT
  --prevjobid=INT ... id of the job to be continued from previous abortion
  --old-sge ... passed to moses-parallel, assume Sun Grid Engine < 6.0
";
  exit 1;
}

# Check validity of input parameters and set defaults if needed

# path of script for running the decoder
$qsubwrapper=dirname($0)."/qsub-wrapper.pl" if !defined $qsubwrapper;
$moses_parallel_cmd = dirname($0)."/hiero-parallel.pl" if !defined $moses_parallel_cmd;
$meteor_parallel_cmd = dirname($0)."/sentence-METEOR.pl" if !defined $meteor_parallel_cmd;
$ter_parallel_cmd = dirname($0)."/sentence-TER.pl" if !defined $ter_parallel_cmd;

die "Error: need to specify the mert directory" if !defined $mertdir;

my $mert_extract_cmd = "$mertdir/pro-extractor.pl";
my $mert_mert_cmd = "$mertdir/PRO.py";

die "Not executable: $mert_extract_cmd" if ! -x $mert_extract_cmd;
die "Not executable: $mert_mert_cmd" if ! -x $mert_mert_cmd;

die "Not executable: $moses_parallel_cmd" if defined $___JOBS && ! -x $moses_parallel_cmd;
die "Not executable: $qsubwrapper" if defined $___JOBS && ! -x $qsubwrapper;
die "Not executable: $___DECODER" if ! -x $___DECODER;
die "Not executable: $meteor_parallel_cmd" if ! -x $meteor_parallel_cmd;
die "Not executable: $ter_parallel_cmd" if ! -x $ter_parallel_cmd;

die "Environmental variable PL_HOME not defined. Exiting!\n" if !defined $ENV{PL_HOME};
die "Environmental variable JAVA_HOME not defined. Exiting!\n" if !defined $ENV{JAVA_HOME};
die "Environmental variable TER_JAR not defined. Exiting!\n" if !defined $ENV{TER_JAR};
die "Environmental variable METEOR_JAR not defined. Exiting!\n" if !defined $ENV{METEOR_JAR};

my $input_abs = ensure_full_path($___DEV_F);
die "Directory not found: $___DEV_F (interpreted as $input_abs)."
  if ! -e $input_abs;
$___DEV_F = $input_abs;


# Option to pass to qsubwrapper and moses-parallel
my $pass_old_sge = $old_sge ? "-old-sge" : "";

my $decoder_abs = ensure_full_path($___DECODER);
die "File not found: $___DECODER (interpreted as $decoder_abs)."
  if ! -x $decoder_abs;
$___DECODER = $decoder_abs;

my $ref_abs = ensure_full_path($___DEV_E);
# check if English dev set (reference translations) exist and store a list of all references
my @references;  
if (-e $ref_abs) {
    push @references, $ref_abs;
}
else {
    # if multiple file, get a full list of the files
    my $part = 0;
    while (-e $ref_abs.$part) {
        push @references, $ref_abs.$part;
        $part++;
    }
    die("Reference translations not found: $___DEV_E (interpreted as $ref_abs)") unless $part;
}
# check if English dev set (reference translations) exist
#die("Reference translations not found: $___DEV_E\n") unless(-e $___DEV_E);

# check if SCFG rules exist
my $scfg_abs = ensure_full_path($___SCFG_RULES);
die "Directory not found: $___SCFG_RULES (interpreted as $scfg_abs)."
  if ! -e $scfg_abs;
$___SCFG_RULES = $scfg_abs;

# Kriya features
my @initLambdas = ();
my @lambdaOrder = ();
my %kriyaFeatsHsh = ( weight_lm => 'lm',
                    weight_glue => 'glue',
                    weight_wp => 'wp',
                    weight_tm => 'tm'
                 );
my %kriyaWgtsHsh = ();
my %initWgts = ();

# set start run
my $start_run = 1;
my $run;
if ($mert_status != 100) {
    $mert_status =~ s/^(\d+)?(\d\d)$/$run=$1;$1.$2/ex;
    $___CONFIG = $___WORKING_DIR."/run$run.moses.ini";
    $run--;
    if (!-e $___CONFIG) { die "Couldn't find config file: $___CONFIG. Exiting!!\n"; }
}
else {
    $run=$start_run-1;
    my $config_abs = ensure_full_path($___CONFIG);
    die "File not found: $___CONFIG (interpreted as $config_abs)."
	if ! -e $config_abs;
    $___CONFIG = $config_abs;
}

# check validity of moses.ini and collect number of models and lambdas per model
my ($models_used) = scan_config($___CONFIG);
$___CONFIG_BAK = $___CONFIG;

# moses should use our config
if ($___DECODER_FLAGS =~ /(^|\s)-(config|f) /
|| $___DECODER_FLAGS =~ /(^|\s)-(ttable-file|t) /
|| $___DECODER_FLAGS =~ /(^|\s)-(distortion-file) /
|| $___DECODER_FLAGS =~ /(^|\s)-(generation-file) /
|| $___DECODER_FLAGS =~ /(^|\s)-(lmodel-file) /
) {
  die "It is forbidden to supply any of -config, -ttable-file, -distortion-file, -generation-file or -lmodel-file in the --decoder-flags.\nPlease use only the --config option to give the config file that lists all the supplementary files.";
}

#store current directory and create the working directory (if needed)
my $cwd = `pawd 2>/dev/null`; 
if(!$cwd){$cwd = `pwd`;}
chomp($cwd);

safesystem("mkdir -p $___WORKING_DIR") or die "Can't mkdir $___WORKING_DIR";

# open local scope
{

    #chdir to the working directory
    chdir($___WORKING_DIR) or die "Can't chdir to $___WORKING_DIR";

    # fixed file names
    my $mert_logfile = "pro.log";
    my $weights_out_file = "weights.txt";

    if ($continue) {
        # die "continue not yet supported by the new mert script\nNeed to load features and scores from last iteration\n";
        # need to load last best values
        print STDERR "Trying to continue an interrupted optimization.\n";
        open IN, "finished_step.txt" or die "Failed to find the step number, failed to read finished_step.txt";
        my $step = <IN>;
        chomp $step;
        $step++;
        close IN;

        if (! -e "run$step.best$___N_BEST_LIST_SIZE.out.gz") {
            # allow stepping one extra iteration back
            $step--;
            die "Can't start from step $step, because run$step.best$___N_BEST_LIST_SIZE.out.gz was not found!"
            if ! -e "run$step.best$___N_BEST_LIST_SIZE.out.gz";
        }

        $start_run = $step +1;

        open IN, "$weights_out_file" or die "Can't read $weights_out_file";
        my $newweights = <IN>;
        chomp $newweights;
        close IN;
        my @newweights = split /\s+/, $newweights;
    }

    my $PARAMETERS;
    $PARAMETERS = $___DECODER_FLAGS;

    my $devbleu = undef;
    my $devribes = undef;
    my $devter = undef;
    my $bestpoint = undef;
    my $zero_nbest_cnt = 0;

    my $cmd;
    # features and scores from the last run.
    my $prev_feature_file=undef;
    my $prev_score_file=undef;
    my $nbest_file=undef;
    if ($mert_status != 100) {
        my $prev_run = $run;
        #if ($prev_run >= 1) {
        #    $prev_feature_file = "run$prev_run.features.dat.gz";
        #    if (!-e $prev_feature_file) { &xtract_past_stats($prev_run); }
        #    print "Using feature and score files from prev iteration: $prev_feature_file\n";
        #}

        my $init_run = 1;
        my $init_wgts_file = "run${init_run}.weights.txt";
        my $init_nbest_file = "run${init_run}.nbest.out";
        @lambdaOrder = get_order_of_scores_from_nbestlist($init_nbest_file, $init_wgts_file);
    }

    while(1) {
        $run++;
        if ($run > $max_runs) {
            print STDOUT "Completed $max_runs runs of tuning with PRO. Stopping!\n";
            last;
        }
        # run beamdecoder with option to output nbestlists
        # the end result should be (1) @NBEST_LIST, a list of lists; (2) @SCORE, a list of lists of lists

        print "run $run start at ".`date`;

        # In case something dies later, we might wish to have a copy
        if ( !-e "./run$run.moses.ini" ) {
            create_config($___CONFIG, "./run$run.moses.ini", $run, (defined$devbleu?$devbleu:"--not-estimated--"), (defined$devribes?$devribes:"--not-estimated--"), (defined$devter?$devter:"--not-estimated--"));
        }

        # skip if the user wanted
        if (!$skip_decoder) {
            print "($run) run decoder to produce n-best lists\n";
            $nbest_file = run_decoder($PARAMETERS, $run);
            if ($run == 1) {
                my $init_wgts_file = "run${run}.weights.txt";
                @lambdaOrder = get_order_of_scores_from_nbestlist($nbest_file, $init_wgts_file);
            }
            #$need_to_normalize = 0;
            #safesystem("gzip -f $nbest_file") or die "Failed to gzip run*out";
            #$nbest_file = $nbest_file.".gz";
        }
        else {
            die "Skipping not yet supported\n";
            #print "skipped decoder run\n";
            #$skip_decoder = 0;
            #$need_to_normalize = 0;
        }

        # extract score statistics and features from the nbest lists
        print STDERR "Scoring the nbestlist.\n";
        my $feature_file = "$___WORKING_DIR/run$run.features.dat";
        my $metric_score_file;
        if ($pro_opt_metric =~ /bleu(\d)/i) { $metric_score_file = "$___WORKING_DIR/Metrics-stats/bleu$1.out.bleu$1"; }
        elsif ($pro_opt_metric =~ /bleu/i) { $metric_score_file = "$___WORKING_DIR/Metrics-stats/bleu.out.bleu"; }
        elsif ($pro_opt_metric =~ /meteor/i) { $metric_score_file = "$___WORKING_DIR/Metrics-stats/meteor.out.meteor"; }
        elsif ($pro_opt_metric =~ /ribes/i) { $metric_score_file = "$___WORKING_DIR/Metrics-stats/ribes.scores.ribes"; }
        elsif ($pro_opt_metric =~ /ter/i) { $metric_score_file = "$___WORKING_DIR/Metrics-stats/ter.scores.ter"; }
        my $run_ref_file = "$___WORKING_DIR/Metrics-stats/run$run.ref.txt";
        my $run_hyp_file = "$___WORKING_DIR/Metrics-stats/run$run.hyp.txt";

        my $nbest_hist_file = "$___WORKING_DIR/all.nbest.out";
        my $new_nbest_file = "$___WORKING_DIR/run$run.nbest.new";
        if ($mert_status =~ /11$/) {
            if (-e $nbest_hist_file) {
                print "Deleting nbest history file: $nbest_hist_file\n";
                safesystem("rm $nbest_hist_file");
            }
        }

        if ($mert_status !~ /12$/) {
            $cmd = "$ENV{PL_HOME}/bin/perl $mert_extract_cmd --refs=".join(",", @references)." --run=$run --work-dir=$___WORKING_DIR --metric=$pro_opt_metric";
            if (defined $___JOBS) {
                safesystem("$qsubwrapper $pass_old_sge -command='$cmd' -queue-parameter=\"$queue_flags\" -stdout=extract.out -stderr=extract.err" )
                or die "Failed to submit extraction to queue (via $qsubwrapper)";
            } else {
                safesystem("$cmd > extract.out 2> extract.err") or die "Failed to do extraction of statistics.";
            }
        }

        # Check the output of PRO extractor; exit if no new candidates are added by the last decoding step
        if (!-s $new_nbest_file) {
            $zero_nbest_cnt++;
            #if ($zero_nbest_cnt >= 3) {
            #    print STDOUT "Decoder did not produce any additional candidates for 3 consecutive iterations. Stopping!\n";
            #    last;
            #}
        }
        else { $zero_nbest_cnt = 0; }

        # run PRO
        $cmd = "/home/baskaran/software/LANG/PYTHON/2.7.3/bin/python $mert_mert_cmd $run $___WORKING_DIR $ref_abs $metric_score_file $pro_sampler $pro_opt_metric";
        if (defined $___JOBS) {
            safesystem("$qsubwrapper $pass_old_sge -command='$cmd' -queue-parameter=\"$queue_flags\"") or die "Failed to start mert (via qsubwrapper $qsubwrapper)";
        } else {
            safesystem("$cmd 2> $mert_logfile") or die "Failed to run mert";
        }
        die "Optimization failed, file $weights_out_file does not exist or is empty"
        if ! -s $weights_out_file;

        # backup copies
        my $next_run = $run + 1;
        #safesystem ("gzip $feature_file; ") or die;
        #safesystem ("gzip $score_file") or die;
        safesystem ("\\cp -f $mert_logfile run$run.$mert_logfile") or die;
        safesystem ("\\cp -f $weights_out_file run$next_run.$weights_out_file") or die; # this one is needed for restarts, too
        print "run $run end at ".`date`;

        $bestpoint = undef;
        $devbleu = undef;
        $devribes = undef;
        $devter = undef;
        open(IN,"$mert_logfile") or die "Can't open $mert_logfile";
        while (<IN>) {
            if (/BLEU =\s*([\d\.]+)/) {
                $devbleu = $1;
            }
            if (/([0-9\.]+) alpha/) {
                $devribes = $1;
            }
            if (/Total TER:\s*([\d\.]+)/) {
                $devter = $1;
                last;
            }
        }
        close IN;

        open(IN, "run$next_run.$weights_out_file");
        while(<IN>) {
            chomp;
            $bestpoint = $_;
            last;
        }
        close(IN);
        #die "Failed to parse pro.log, missed Best point there."
        #if !defined $bestpoint || !defined $devbleu || !defined $devter;
        print "($run) BEST at $run: $bestpoint => BLEU: $devbleu, RIBES: $devribes, TER: $devter at ".`date`;
        $mert_status = ($run + 1)."00";

        my $w_ind;
        my $label;
        my @newweights = split /\s+/, $bestpoint;
        my @vals;
        for ($w_ind = 0; $w_ind < scalar(@lambdaOrder); $w_ind++) {
            $label = $lambdaOrder[$w_ind];
            if ($w_ind == 0) {
                @vals = ();
            }
            elsif ($label ne $lambdaOrder[$w_ind - 1]) {
                $kriyaWgtsHsh{$lambdaOrder[$w_ind - 1]} = join(" ", @vals);
                @vals = ();
            }
            push (@vals, $newweights[$w_ind]);
        }
        $kriyaWgtsHsh{$label} = join(" ", @vals);

        open F, "> finished_step.txt" or die "Can't mark finished step";
        print F $run."\n";
        close F;

        #$prev_feature_file = $feature_file.".gz";
        #$prev_score_file = $score_file.".gz";
        #safesystem("\\rm -f run$run.out") or die;

    }
    print "Training finished at ".`date`;

    safesystem("\\cp -f $mert_logfile run$run.$mert_logfile") or die;

    create_config($___CONFIG_BAK, "./moses.ini", $run, $devbleu, $devribes, $devter);

    # just to be sure that we have the really last finished step marked
    open F, "> finished_step.txt" or die "Can't mark finished step";
    print F $run."\n";
    close F;

    #chdir back to the original directory # useless, just to remind we were not there
    chdir($cwd);

} # end of local scope


sub how_many_lines {
    my $in_file = shift;
    my $tot_lines = 0;
    open(IF, $in_file);
    while(<IF>) {
        $tot_lines++;
    }
    close(IF);
    return $tot_lines;
}

sub xtract_past_stats {
    my $prev_run = shift;
    my $curr_nbest_file;
    my $curr_feature_file = "";
    my $curr_score_file = "";
    my $past_feature_file;
    my $past_score_file;
    my $cmd;
    my $r;

    print STDERR "\n###\nINFO: Extracting feature and score files for earlier runs ...\n###\n";
    for ($r=1; $r<=$prev_run; $r++) {
        $curr_nbest_file = "run${r}.nbest.out.gz";
        if (!-e $curr_nbest_file) {
            if(!-e "run${r}.nbest.out") {
                die "For resuming MERT after interruption either nbest files or feature and score files from earlier runs are required. Exiting!!\n";
            }
            safesystem("gzip -f run${r}.nbest.out") or die "Failed to gzip run*out";
        }

        $curr_feature_file = "run${r}.features.dat";
        $curr_score_file = "run${r}.scores.dat";
        $cmd = "$ENV{PL_HOME}/bin/perl $mert_extract_cmd --refs=".join(",", @references)." --run=$run --work-dir=$___WORKING_DIR";
        #if (defined $past_feature_file) { $cmd = $cmd." --prev-ffile $past_feature_file"; }
        #if (defined $past_score_file) { $cmd = $cmd." --prev-scfile $past_score_file"; }
        if (defined $___JOBS) {
            safesystem("$qsubwrapper $pass_old_sge -command='$cmd' -queue-parameter=\"$queue_flags\" -stdout=extract.out -stderr=extract.err" )
                        or die "Failed to submit extraction to queue (via $qsubwrapper)";
        } else {
            safesystem("$cmd > extract.out 2> extract.err") or die "Failed to do extraction of statistics.";
        }

        safesystem ("gzip $curr_feature_file; ") or die;
        safesystem ("gzip $curr_score_file") or die;
        $past_feature_file = $curr_feature_file.".gz";
        $past_score_file = $curr_score_file.".gz";
    }
}


sub run_decoder {
    my ($parameters, $run) = @_;
    my $filename_template = "run%d.nbest.out";
    my $filename = sprintf($filename_template, $run);
    
    print "params = $parameters\n";
    # prepare the decoder config:
    my $decoder_config = "";
    print STDERR "DECODER_CFG = $decoder_config\n";

    # run the decoder
    my $nBest_cmd = "-n-best-size $___N_BEST_LIST_SIZE";
    my $decoder_cmd;

    if (defined $___JOBS) {
        if ( -f $___SCFG_RULES ) {              # For specifying the ttable-file directly
            $decoder_cmd = "$moses_parallel_cmd $pass_old_sge -config $___CONFIG -kriya-options \"$kriya_opts\" -qsub-prefix mert$run -queue-parameters \"$queue_flags\" -mert-status $mert_status -prev-jobid $prev_jobid -n-best-list $filename -n-best-size $___N_BEST_LIST_SIZE -input-dir $___DEV_F -output-dir $___WORKING_DIR --ttable-file $___SCFG_RULES --lmfile $___LM_FILE -jobs $___JOBS -decoder-prefix $___DECODER_PREFIX -decoder $___DECODER -nodes-prop \"$nodes_prop\" > run$run.out";
        }
        elsif ( -d $___SCFG_RULES ) {           # For specifying the rule-dir having the ttable-files
            $decoder_cmd = "$moses_parallel_cmd $pass_old_sge -config $___CONFIG -kriya-options \"$kriya_opts\" -qsub-prefix mert$run -queue-parameters \"$queue_flags\" -mert-status $mert_status -prev-jobid $prev_jobid -n-best-list $filename -n-best-size $___N_BEST_LIST_SIZE -input-dir $___DEV_F -output-dir $___WORKING_DIR -rule-dir $___SCFG_RULES --lmfile $___LM_FILE -jobs $___JOBS -decoder-prefix $___DECODER_PREFIX -decoder $___DECODER -nodes-prop \"$nodes_prop\" > run$run.out";

            #$decoder_cmd = "$moses_parallel_cmd $pass_old_sge -config $___CONFIG -kriya-options \"$kriya_opts\" -qsub-prefix mert$run -queue-parameters \"$queue_flags\" -decoder-parameters \"$parameters $decoder_config\" -mert-status $mert_status -prev-jobid $prev_jobid -n-best-list $filename -n-best-size $___N_BEST_LIST_SIZE -input-dir $___DEV_F -output-dir $___WORKING_DIR -rule-dir $___SCFG_RULES --lmfile $___LM_FILE -jobs $___JOBS -decoder-prefix $___DECODER_PREFIX -decoder $___DECODER -nodes-prop \"$nodes_prop\" > run$run.out";
        }
    } else {
      my $sentIndex = 100;
      my $in_file = $___DEV_F;
      my $rule_file = $___SCFG_RULES;
      my $out_file = $___WORKING_DIR."/".$sentIndex.".out";
      $sentIndex = 0;       # Reset the sentIndex to 1
      $decoder_cmd = "$___DECODER_PREFIX $___DECODER $parameters --config $___CONFIG $kriya_opts --index $sentIndex --inputfile $in_file --outputfile $filename --glue-file $___GLUE_RULES --ttable-file $rule_file --lmodel-file $___LM_FILE > run$run.out";
#      $decoder_cmd = "$___DECODER_PREFIX $___DECODER $parameters --config $___CONFIG $decoder_config -n-best-list $filename $___N_BEST_LIST_SIZE -i $___DEV_F > run$run.out";
    }

    safesystem($decoder_cmd) or die "The decoder died. CONFIG WAS $decoder_config \n";
    $prev_jobid = 0;

    # we have checked the nbestlist already, we trust the order of output scores does not change
    return $filename;
}

sub get_order_of_scores_from_nbestlist {
    # read the first line and interpret the ||| label: num num num label2: num ||| column in nbestlist
    # return the score labels in order
    my $fname_or_source = shift;
    my $init_wgts_file = shift;

    print STDERR "Peeking at the beginning of nbestlist to get order of scores: $fname_or_source\n";
    open IN, $fname_or_source or die "Failed to get order of scores from nbestlist '$fname_or_source'";
    my $line = <IN>;
    close IN;
    die "Line empty in nbestlist '$fname_or_source'" if !defined $line;
    my ($sent, $hypo, $scores, $total) = split /\|\|\|/, $line;
    $scores =~ s/^\s*|\s*$//g;
    die "No scores in line: $line" if $scores eq "";

    my @order = ();
    my $label = undef;
    foreach my $tok (split /\s+/, $scores) {
        if ($tok =~ /^([a-z][0-9a-z]*):/i) {
            $label = $1;
            push @initLambdas, $initWgts{$label};
        } elsif ($tok =~ /^-?[-0-9.e]+$/) {
            # a score found, remember it
            die "Found a score but no label before it! Bad nbestlist '$fname_or_source'!" if !defined $label;
            push @order, $label;
        } else {
            die "Not a label, not a score '$tok'. Failed to parse the scores string: '$scores' of nbestlist '$fname_or_source'";
        }
    }
    print STDERR "The decoder returns the scores in this order: @order\n";

    if (!-e $init_wgts_file) {
        open OUT, ">$init_wgts_file" or die "Failed to open file $init_wgts_file for writing\n";
        print OUT join(" ", @initLambdas), "\n";
        close(OUT);
    }

    return @order;
}

sub create_config {
    my $infn = shift;               # source config
    my $outfn = shift;              # where to save the config
    my $iteration = shift;          # just for verbosity
    my $bleu_achieved = shift;
    my $ribes_achieved = shift;
    my $ter_achieved = shift;

    my %P; # the hash of all parameters we wish to override

    # first convert the command line parameters to the hash
    { # ensure local scope of vars
    	my $parameter=undef;
	    print "Parsing --decoder-flags: |$___DECODER_FLAGS|\n";
        $___DECODER_FLAGS =~ s/^\s*|\s*$//;
        $___DECODER_FLAGS =~ s/\s+/ /;
	    foreach (split(/ /,$___DECODER_FLAGS)) {
	        if (/^\-([^\d].*)$/) {
		        $parameter = $1;
	        }
	        else {
                die "Found value with no -paramname before it: $_"
                if !defined $parameter;
		        push @{$P{$parameter}},$_;
	        }
	    }
    }
    my $shortname = undef;
    my @newweights = ();

    # create new moses.ini decoder config file by cloning and overriding the original one
    if ($mert_status !~ /^[^1]\d\d$/ && -e $___CONFIG) {
	    print STDERR "$infn\n";
	    print STDERR "Config file $___CONFIG exists. Not copying the initial config file\n";
    }

    open(INI,$infn) or die "Can't read $infn";
    delete($P{"config"}); # never output 
    print "Saving new config to: $outfn\n";
    open(OUT,"> $outfn") or die "Can't write $outfn";
    print OUT "# MERT optimized configuration\n";
    print OUT "# decoder $___DECODER\n";
    print OUT "# BLEU $bleu_achieved/ RIBES $ribes_achieved/ TER $ter_achieved on dev $___DEV_F\n";
    print OUT "# We were before running iteration $iteration\n";
    print OUT "# finished ".`date`;
    my $line = <INI>;
    while(1) {
	    last unless $line;

	    # skip until hit [parameter]
	    if ($line !~ /^\[(.+)\]\s*$/) { 
	        $line = <INI>;
    	    print OUT $line if $line =~ /^\#/ || $line =~ /^\s+$/;
	        next;
	    }

    	# parameter name
	    my $parameter = $1;
	    print OUT "[$parameter]\n";

        if (exists $kriyaFeatsHsh{$parameter}) {
            $shortname = $kriyaFeatsHsh{$parameter};
            if (exists $kriyaWgtsHsh{$shortname}) {
                @newweights = split(/\s+/, $kriyaWgtsHsh{$shortname});
                foreach my $new_wgt (@newweights) {
                    print OUT "$new_wgt\n";
                    $line = <INI>;
                }
            }
            else { die "ERROR: Feature $parameter having shortname $shortname doesn't have corresponding weight(s). Exiting!!\n"; }
            next;
        }

    	# change parameter, if new values
	    if (defined($P{$parameter})) {
    	    # write new values
	        foreach (@{$P{$parameter}}) {
		        print OUT $_."\n";
	        }
	        delete($P{$parameter});
	        # skip until new parameter, only write comments
	        while($line = <INI>) {
		        print OUT $line if $line =~ /^\#/ || $line =~ /^\s+$/;
		        last if $line =~ /^\[/;
		        last unless $line;
	        }
	        next;
	    }

        # unchanged parameter, write old
	    while($line = <INI>) {
	        last if $line =~ /^\[/;
	        print OUT $line;
	    }
    }

    # write all additional parameters
    foreach my $parameter (keys %P) {
	    print OUT "\n[$parameter]\n";
	    foreach (@{$P{$parameter}}) {
	        print OUT $_."\n";
	    }
    }

    close(INI);
    close(OUT);
    print STDERR "Saved: $outfn\n";
    $___CONFIG = $outfn;
}

sub safesystem {
  print STDERR "Executing: @_\n";
  system(@_);
  if ($? == -1) {
      print STDERR "Failed to execute: @_\n  $!\n";
      exit(1);
  }
  elsif ($? & 127) {
      printf STDERR "Execution of: @_\n  died with signal %d, %s coredump\n",
          ($? & 127),  ($? & 128) ? 'with' : 'without';
      exit(1);
  }
  else {
    my $exitcode = $? >> 8;
    print STDERR "Exit code: $exitcode\n" if $exitcode;
    return ! $exitcode;
  }
}

sub ensure_full_path {
    my $PATH = shift;
    $PATH =~ s/\/nfsmnt//;
    return $PATH if $PATH =~ /^\//;
    my $dir = `pawd 2>/dev/null`; 
    if(!$dir){$dir = `pwd`;}
    chomp($dir);
    $PATH = $dir."/".$PATH;
    $PATH =~ s/[\r\n]//g;
    $PATH =~ s/\/\.\//\//g;
    $PATH =~ s/\/+/\//g;
    my $sanity = 0;
    while($PATH =~ /\/\.\.\// && $sanity++<10) {
        $PATH =~ s/\/+/\//g;
        $PATH =~ s/\/[^\/]+\/\.\.\//\//g;
    }
    $PATH =~ s/\/[^\/]+\/\.\.$//;
    $PATH =~ s/\/+$//;
    $PATH =~ s/\/nfsmnt//;
    return $PATH;
}

sub scan_config {
    my $ini = shift;
    print "Scanning file: $ini\n\n";
    my $inishortname = $ini; $inishortname =~ s/^.*\///; # for error reporting

    open INI, $ini or die "Can't read $ini";

    my $section = undef;  # name of the section we are reading
    my $shortname = undef;  # the corresponding short name
    my @vals = ();
    my $nr = 0;
    my $error = 0;
    while (<INI>) {
        chomp;
        $nr++;
        if (defined $shortname) {
            if ($_ =~ /^\s*$|^\s*#/) {
                $initWgts{$shortname} = join(" ", @vals);
                $kriyaWgtsHsh{$shortname} = $initWgts{$shortname};
                $shortname = undef;
                @vals = ();
            }
            else {
                push (@vals, $_);
            }
            next;
        }

        next if /^\s*#/; # skip comments
        if (/^\[([^\]]*)\]\s*$/) {
            $section = $1;
            if ($section =~ /^weight/) {
                if (exists $kriyaFeatsHsh{$section}) {
                    $shortname = $kriyaFeatsHsh{$section};
                }
            }
            next;
        }
    }
    exit(1) if $error;
}

