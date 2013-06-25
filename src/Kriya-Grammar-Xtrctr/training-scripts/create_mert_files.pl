#!/usr/bin/perl

use Cwd 'abs_path';
use File::Basename;
use lib dirname(abs_path($0));
use POSIX;

use TrainConfig;
use strict;
use warnings;

my $config_file = $ARGV[0];
my $dev_split = $ARGV[1];
my $test_split = $ARGV[2];

if (!defined $config_file) { die "usage: $0 <Training config file>\nSpecify a training config file. Exiting!\n"; }
if (!-e $config_file) { die "Training config file $config_file does not exist. Exiting!\n"; }

if(!defined $dev_split) { $dev_split = 0; }
if(!defined $test_split) { $test_split = 0; }

my $cfg = TrainConfig->new($config_file);

my $model_root = $cfg->{KRIYA_MODELS};                                  # training - root directory
my $model_dir = "$model_root/model";                                    # where to find the models
my $tune_dir = "$model_root/tuning";                                    # tuning directory (for config file)
(-e $tune_dir) ? die "ERROR: Kriya tuning directory $tune_dir already exists. Exiting!\n" : safeSystem("mkdir $tune_dir");

my $kriya_mert_dir = "$cfg->{KRIYA_DEC}/mert-scripts";
die "kriya.glue template file couldn't be read or doesn't exist in $kriya_mert_dir. Exiting!\n" if (!-e "${kriya_mert_dir}/kriya.glue");

my $kriya_tune_scrpt;
if ($cfg->{optimizer} =~ /^mert$/i) {
    $kriya_tune_scrpt = "run_mert.kriya.sh";
    die "A template script $kriya_tune_scrpt couldn't be read or doesn't exist in $kriya_mert_dir. Exiting!\n" if(!-e "${kriya_mert_dir}/${kriya_tune_scrpt}");
    if ($cfg->{which_mert} eq 'zmert') {
        print STDERR "Automatic script creation doesn't support zMERT yet. Creating script for running Moses MERT ...\n";
    }
}
elsif ($cfg->{optimizer} =~ /^pro$/i) {
    $kriya_tune_scrpt = "run_pro.kriya.sh";
    die "A template script $kriya_tune_scrpt couldn't be read or doesn't exist in $kriya_mert_dir. Exiting!\n" if(!-e "${kriya_mert_dir}/${kriya_tune_scrpt}");
}

my $kriya_glue;
&copy_glue();
&create_config();

my $tune_scrpt = &create_tuning_script();

print STDERR "INFO: Kriya training is now complete.\n";
print STDERR "    * Run $tune_scrpt to run $cfg->{optimizer}\n";


# Copy the glue file #
sub copy_glue {
    my $glue_template = "$kriya_mert_dir/kriya.glue";
    $kriya_glue = "$tune_dir/kriya.glue";

    print STDERR "Creating the kriya.glue glue rules file ...\n";
    open(GT, "$glue_template");
    open(GL, ">$kriya_glue");
    while(<GT>) {
        chomp;
        print GL "$_\n";
    }
    close(GL);
    close(GT);
}


# Create the config file for tuning step #
sub create_config {
    my $kriya_cfg = "$tune_dir/kriya.ini";

    print STDERR "Creating the kriya.ini config file ...\n";
    open(INI, ">$kriya_cfg");
    print INI "\n#########################\n### KRIYA CONFIG FILE ###\n";
    print INI "##### Used for MERT #####\n#########################\n\n";
    print INI "[hiero-options]\n";
    print INI "shallow-hiero = $cfg->{shallow_hiero}\n";
    print INI "use-srilm = $cfg->{use_srilm}\n";
    print INI "fr-rule-terms = $cfg->{fr_side_len}\n";
    print INI "cbp = $cfg->{cbp}\n\n";

    print INI "[sentperfile]\n$cfg->{sent_per_file}\n\n";

    print INI "[lmodel-file]\n$cfg->{lm_order} $cfg->{lm_file}\n\n" if (defined $cfg->{lm_file});

    print INI "[glue-file]\n$kriya_glue\n\n";

    print INI "# Various feature weights\n";
    print INI "# language model weights\n[weight_lm]\n1.0\n\n";
    print INI "# translation model weights\n[weight_tm]\n1.066893 0.752247 0.589793 0.589793 1.0\n\n";
    print INI "# word penalty\n[weight_wp]\n-2.844814\n\n";
    print INI "# glue weight\n[weight_glue]\n1.0\n\n";

    print INI "[n-best-list]\nnbest-size = $cfg->{nbest_size}\nnbest-format = $cfg->{nbest_format}\n\n";
    close(INI);
}


# Create the script for tuning with MERT/ PRO #
sub create_tuning_script {
    my $template_scrpt;
    my $tune_scrpt;

    if ($cfg->{optimizer} =~ /^pro$/i) {
        $template_scrpt = "$kriya_mert_dir/$kriya_tune_scrpt";
        $tune_scrpt = "$model_root/$kriya_tune_scrpt";
    }
    elsif ($cfg->{optimizer} =~ /^mert$/i) {
        $template_scrpt = "$kriya_mert_dir/$kriya_tune_scrpt";
        $tune_scrpt = "$model_root/$kriya_tune_scrpt";
    }

    my $line = "";
    my $lang_pair = "$cfg->{src}-$cfg->{tgt}";
    my $ref_file_dev = "$cfg->{LC_DEV_DIR}/all.$lang_pair.$cfg->{tgt}";
    my $ref_file_test = "$cfg->{LC_TEST_DIR}/all.$lang_pair.$cfg->{tgt}";

    print STDERR "Creating the script run_{pro|mert}.kriya.sh for running PRO/Moses-MERT ...\n";
    open(ST, $template_scrpt);
    open(MRT, ">$tune_scrpt");
    while(<ST>) {
        chomp;
        if ($_ =~ /(^#|^$)/) { print MRT "$_\n"; next; }

        $line = $_;
        if ($_ =~ /^mert_dir/ && $cfg->{optimizer} =~ /^mert$/i) { $line = &plug_val_4_param($line, $cfg->{MERT_BIN}); }
        elsif ($_ =~ /^d_dir/) { $line = &plug_val_4_param($line, $cfg->{KRIYA_DEC}); }
        elsif ($_ =~ /^curr_dir/) { $line = &plug_val_4_param($line, $model_root); }
        elsif ($_ =~ /^dev_src/) { $line = &plug_val_4_param($line, "$model_dir/devset-sent"); }
        elsif ($_ =~ /^dev_ref/) { $line = &plug_val_4_param($line, $ref_file_dev); }
        elsif ($_ =~ /^dev_scfg/) { $line = &plug_val_4_param($line, "$model_dir/devset-rules"); }
        elsif ($_ =~ /^dev_split/) { $line = &plug_val_4_param($line, $dev_split); }
        elsif ($_ =~ /^test_src/) { $line = &plug_val_4_param($line, "$model_dir/testset-sent"); }
        elsif ($_ =~ /^test_ref/) { $line = &plug_val_4_param($line, $ref_file_test); }
        elsif ($_ =~ /^test_scfg/) { $line = &plug_val_4_param($line, "$model_dir/testset-rules"); }
        elsif ($_ =~ /^test_split/) { $line = &plug_val_4_param($line, $test_split); }
        elsif ($_ =~ /^lm/) { $line = &plug_val_4_param($line, $cfg->{lm_file}); }
        elsif ($_ =~ /^pro_metric/ && $cfg->{optimizer} =~ /^pro$/i) { $line = &plug_val_4_param($line, $cfg->{opt_metric}); }
        elsif ($_ =~ /^pro_sampler/ && $cfg->{optimizer} =~ /^pro$/i) { $line = &plug_val_4_param($line, $cfg->{opt_sampler}); }
        print MRT "$line\n";
    }
    close(MRT);
    close(ST);

    return $tune_scrpt;
}


# Plug in the new parameter value in a line
sub plug_val_4_param {
    my $line = shift;
    my $param_val = shift;
    my $cmnt = "";

    my ($key, $val) = split(/=/, $line);
    $val =~ s/(\s+#.*)/$cmnt=$1;/e;
    return "${key}=${param_val}${cmnt}";
}


sub safeSystem {
    print "   * About to Execute : @_\n";
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
}

