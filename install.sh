#stript to simplify installation
#Assumes that we run on a Debian-like system, using 'apt' to install things using sudo

env_dir=coverup_venv

sudo apt install python3-venv

rm -rf $env_dir 

#Create virtual environment
#/usr/bin/python3 -m venv coverup_venv
/usr/bin/python -m venv $env_dir

source $env_dir/bin/activate

pip install -r requirements.txt

# Create the pdfanon script in /usr/local/bin
sudo echo "
#!/bin/bash

if [ ! -n \"\$1\" ]
then
  echo \"Usage: \$0 file.pdf\"
  exit \$E_BADARGS
fi
pdf=\$1

path=$PWD
source \$path/$env_dir/bin/activate
\$path/CoverUP.py \$pdf
" > /usr/local/bin/pdfanon

