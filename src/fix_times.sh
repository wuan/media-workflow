#!/bin/bash

for file in $(find 2025/09_fix -name "*.jpg"); do
	echo $file
	exiftool -overwrite_original "-alldates+=0:0:0 1:0:0" $file
        exiftool -v -if '$Make and $Model and $DateTimeOriginal' -m -d '%Y/%m/%Y%m%d_%H%M%S' -P '-filename<${DateTimeOriginal}_${Make;tr/ /-/;s/--+/-/g}_${Model;tr/ /-/;s/--+/-/g}%+c.${FileTypeExtension}' $file
done

#exiftool -if '$Make and $Model and $GpsDateTime' -m -d '%Y/%m/%Y%m%d_%H%M%S' -P '-filename<${GpsDateTime}_${Make;tr/ /-/;s/--+/-/g}_${Model;tr/ /-/;s/--+/-/g}%+c.${FileTypeExtension}' $SOURCE