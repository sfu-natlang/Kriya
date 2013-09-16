---
layout: post
title: Kriya step-by-step documentation
---

**What is Kriya**


Kriya is an in-house hierarchical phrase-based system, written from scratch by Baskaran Sankaran. It is mostly in Python, with some scripts in Perl.
There were other existing hierarchical phrase-based systems (e.g Joshua, cdec), but, they were not in Python. Our aim is to have something that is readable
and makes it easy for new users to contribute. 




**Before getting started**

Check that Kriya is downloaded.

The *.config file is the main file.
The options should be correctly set. 
The environment variables in caps make sense from their names.
Set them correctly to the Kriya paths. 

Make max_phr_len = 7 if you want to compare to Moses. 

Change the qsub_notify variable to your email ID. This ensures that each job sends an email to the given ID. It is very helpful if any of your jobs fail. The email mentions the reasons to a reasonable level of detail. 

If you want to split the training data into more parts, the option is split\_size.

If you want the dev/test files into more parts, the option is sent\_per\_file.
keep this at 50. the reason is that when your dev file has, say, 2000 lines ( standard for nice, clean europarl languages), then, 
with 200, you create 10 files. When you run MERT, it runs 10 jobs in parallel. Decoding and the MERT algorithm is slow. The more parallel jobs that run, the 
faster it is for you. Keep it at 50. 50 is a sweet spot, of sorts.



**The Moses 5**

The Hiero pipeline starts to get different only after getting the initial phrase alignments. You get the phrase alignments the same way as phrase-based systems. Hence, with Kriya, either you let Kriya call Moses internally or you can call Moses yourself and supply Kriya with the initial phrase-alignments. Here, lets discuss the Moses steps you would do separately and what Kriya expects in terms of directory structure. 

<pre>
rdholaki@vinken toy-fr-en]$ mkdir -p training/pre-processed/lc-dev training/pre-processed/lc-train training/pre-processed/lc-test
</pre>

This creates lc-dev, lc-train and lc-test inside training/pre-processed. All your output files go inside training/. There are other parts to the training/ folder which will come up gradually. 

Now, you do the tokenization, lowercasing and the cleaning corpus. These steps are obvious, but, lets cover them anyway. 

<pre>
    [rdholaki@vinken toy-fr-en]$ $SCRIPTS_ROOTDIR/tokenizer/tokenizer.perl -l fr < corpus/train/news-commentary-v6.fr-en.fr > training/pre-processed/lc-train/news-commentary-v6.fr-en.fr.tok
    Tokenizer Version 1.0
    Language: fr
</pre>

<pre>

    [rdholaki@vinken toy-fr-en]$ $SCRIPTS_ROOTDIR/tokenizer/tokenizer.perl -l en < corpus/train/news-commentary-v6.fr-en.en > training/pre-processed/lc-train/news-commentary-v6.fr-en.en.tok
    Tokenizer Version 1.0
    Language: en
</pre>

<pre>
    [rdholaki@vinken toy-fr-en]$ $SCRIPTS_ROOTDIR/tokenizer/lowercase.perl < training/pre-processed/lc-train/news-commentary-v6.fr-en.fr.tok > training/pre-processed/lc-train/news-commentary-v6.fr-en.fr.lower
</pre>

<pre>
    [rdholaki@vinken toy-fr-en]$ $SCRIPTS_ROOTDIR/tokenizer/lowercase.perl < training/pre-processed/lc-train/news-commentary-v6.fr-en.en.tok > training/pre-processed/lc-train/news-commentary-v6.fr-en.en.lower
</pre>

Now, you repeat this process for your lc-dev and lc-test directory. As you can see, its tedious. There are two easy ways out. One, write your own shell script which does these steps. Or let Kriya take care of this for you. Kriya runs phr_xtract.pl which does these set of steps. All Kriya wants are the set of right paths. And the moses module to be loaded. 

Assuming you have lowercased and tokenized and cleaned your data, time comes to get the alignments from Moses. 

<pre>
    $SCRIPTS_ROOTDIR/training/train-model.perl --parts $parts --parallel --first-step 1 --last-step 5 -alignment grow-diag-final-and >& training.out &
</pre>

You only need the alignments. You don't need the scores, or the reordering. Hence, we have the --first-step and --last-step.
 When doing training on larger datasets, it helps to divide it into parts and do training in parallel.
  --parallel option means that giza++ learns the forward and backward alignments happens simultaneously. These options decrease the training time manifold. 

Note that you are not required to run the steps above the way its been outlined. Kriya's script phr\_xtract.pl runs the steps outlined above. The steps were written
down so that you know what is going on in the script. 

In practice, scfg_xtract.pl script does all the 4 steps related to training pipeline. 

When you run either of the two  scripts, scfg_xtract.pl or the tuning script, Kriya creates a script directory where each of the scripts that have been run, 
are written in a separate file. To explain with an example, consider step 0 of scfg\_xtract.pl. It uses the "extract" command in moses. 
Say, that step went wrong in your Kriya run and you want to debug what could have happened. 
The first thing you would want to find out is what exact command was run with the paths. You look at the file scripts/extract.sh.


<pre>
	#! /bin/tcsh 

/cs/natlang-sw/Linux-x86_64/NL/MT/MOSES/SVN_20101028/scripts/training/phrase-extract/extract /cs/natlang-projects/users/rdholakia/Hiero-Triangulation/baseline-bigLM/training/pre-processed/lc-train/all.ht-en.en /cs/natlang-projects/users/rdholakia/Hiero-Triangulation/baseline-bigLM/training/pre-processed/lc-train/all.ht-en.ht /cs/natlang-projects/users/rdholakia/Hiero-Triangulation/baseline-bigLM/training/phr-alignments/model/aligned.grow-diag-final-and temp.ht-en 10 --OnlyOutputSpanInfo > /cs/natlang-projects/users/rdholakia/Hiero-Triangulation/baseline-bigLM/training/phr-alignments/moses/all.ht-en.outspan
rm -rf /local-scratch/${PBS_JOBID}

</pre>

So, this command was run. You can now see if the module path could be wrong ( you loaded the wrong module), or the file paths could be wrong ( check the config file) 
and so on. The same thing can be done for any phase. Just look at the scripts/ directory and you should be able to find the file that will have the exact command
that was run. 

For the sake of completeness, lets discuss a little bit about the various phases in scfg_xtract. Phase 0 uses the moses extract command. This uses the forward and backward 
alignment files to extract phrase pairs. It also creates some of the files and the directories.
 Also, it creates a training/phr-alignments/moses directory. 
 based on what number you gave for split\_size, it creates
 that many sub-files. So, inside training/phr-alignments/moses, 
 you will find *.outspan files, and a complete file, that is, 
 all.src-tgt.outspan.  

 In Phase 1, we use the main SCFG extraction algorithm to extract phrase pairs with non-terminals, as explained in Chiang '05, 
Chiang '07. This extracts all possible SCFG rules. This uses the script __SCFG\_ph1.py_  script. In phase 1b, the target counts are consolidated ( the extraction is done in 
parts ). In Phase 2,  there is phase 2a, 2b and 2c. As part of phase 2a, you filter the phrase table based on dev set. As part of 2b, you compute
the consolidated counts and the forward/backward probabilities.  Now, the following is important.  The Hiero models can get quite large. To keep the size in check, we filter our phrase table based on the development 
set and the test set. . But, what do you do if you need the complete phrase table, one without the filtering based on dev and test ? 
This gives rise to another question. Why would you even need a full phrase table ?! 

You would need one for, say, triangulation. If you are making a phrase table between source and any of the intermediate languages, or between any of the intermediate 
languages, then, you will not want to ``tune'' your phrase table. All you need are the entries, and all of them. This is just one of the cases where you would want 
a complete non-filtered phrase table.  Look at an entry below to get an explanation for how to do that. 

Coming back to the steps. You filter the phrase tables, then, you generate the rules based on the development and test set, and finally, to end, you generate the tuning
script, which is either PRO or MERT. Quite a few things are taken care of by one perl script, eh ?




        


Here, observe the kriya.ini file. The initial weights should be in a single line and not new-line separated like moses. This was a bug that i had run into,
was fixed. But, just to ensure that your tuning jobs do not fail, ensure that the feature weights are in the correct format ( single line).

 And then, if you see the run\_mert\_kriya.sh, ( or run\_pro\_kriya.sh ), most of the things are taken care of. Just, see that the time taken for each job is 
 proper, according to your split. To be on the safe side, assuming that your jobs will be run of files of length 50, keep the walltime at 2:00:00 or nearabouts.
 Note that this is dependent on your data, your language pair and so on. On unclean data, the decoding can be faster as there are not that many options. 
 With French, it can be more time-consuming. TO be on the safe side, keep it a little higher. 

 Also, you will see that not all the tuning jobs take the same amount of time. This is perfectly okay. Decoding some sentences can take longer than others. 
 Not all of them will even use up the 100-best list that you refer to. So, this is alright. 

 Also, the language model is important. There is a default filler in the kriya.ini file. If you don't want that one, point it to the correct language model. 

 It is important that you define some environment variables. NGRAM\_SWIG\_SRILM, NGRAM\_SWIG\_KENLM, PL\_HOME, PY\_HOME. the first two are for the swig wrappers, 
 PL\_HOME is assumed to point to the perl implementation, and PY\_HOME to the python implementation. You also need to set METEOR\_JAR and TER\_JAR.  When you run tuning, we use some third-party evaluators, namely, METEOR and TER. They are not released as part of Kriya. Download them separately and point
 to their jar files or Kriya would give an error about their absence.  

 The colony cluster and our lab cluster use tcsh as the default shell. Set these variables in your ~/.tcshrc file. tcsh expects variables to be defined 
 as 
 <pre>
  setenv variable-name variable-value 
</pre>.  

 DO not do it the way you do it in bash. (export variable-name=variable-value)

 Set these variables before you run the tuning. But, but, note that if you have also set your MOSES\_DIR, SCRIPTS\_ROOTDIR variables in your tcshrc file, 
 unset them. Otherwise Kriya will complain that those are already set and it will exit. If you use modules, do module unload for moses before you start tuning. Learn how to deal with environment variables. You can use them effectively. 



 



