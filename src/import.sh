#!/bin/bash

SOURCE=../photos_incoming

exiftool -v -fast2 -if '$Make and $Model and $DateTimeOriginal' -m -d '%Y/%m/%Y%m%d_%H%M%S' -P '-filename<${DateTimeOriginal}${SubSecTimeOriginal;$_ = $_ ? "." . $_ : ""}_${Make;tr/ /-/;s/--+/-/g}_${Model;tr/ /-/;s/--+/-/g}%+c.${FileTypeExtension}' $SOURCE

#exiftool -v -if '$Make and $Model and $GpsDateTime' -m -d '%Y/%m/%Y%m%d_%H%M%S' -P '-filename<${GpsDateTime}${SubSecTime;$_ = $_ ? "." . $_ : ""}_${Make;tr/ /-/;s/--+/-/g}_${Model;tr/ /-/;s/--+/-/g}%+c.${FileTypeExtension}' $SOURCE