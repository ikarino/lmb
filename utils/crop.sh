#!/bin/sh
convert $5 -crop $3x$4+$1+$2 $6 && open $6
