#!/bin/sh

[ -r /var/env.cache ] && . /var/env.cache

# Make sure that no command accidentally writes stdout or stderr stuff into
# the output stream = tar archive. File descriptor 3 is the real output.
exec 3>&1 > /dev/null 2>&1

FAIL=
fail() {
	[ -z "$FAIL" ] && FAIL="$@"
}

export SICPW="${QUERY_STRING##*password_restore=}"
[ -z "$CONFIG_LABOR_ID_NAME" ] && REV="" || REV="-$(sed -nr 's/.*[ ^]*CONFIG_BUILDNUMBER="?([^"]*).*/\1/p' /etc/init.d/rc.conf)"
fname="$(echo ${CONFIG_PRODUKT_NAME}_${CONFIG_VERSION_MAJOR}.${CONFIG_VERSION}${REV}-$(cat /etc/.freetz-version)$(date '+_%Y-%m-%d_%H%M')_settings${SICPW:+.crypted}.tar | tr ' !' '_.')"

# Create temp-dirs for backup
OUTER_DIR="/tmp/settings.tmp.backup"
INNER_DIR="$OUTER_DIR/var_flash"
rm  -rf  "$OUTER_DIR"
mkdir -p "$INNER_DIR" || fail "$(lang de:"Fehler beim Erstellen des Verzeichnisses" en:"Erron on creating directory")"

# Create additional files
sort /proc/sys/urlader/environment | sed -rn "s/^(SerialNumber|maca|tr069_passphrase|wlan_key)[ \t]*//p" | md5sum | sed 's/ .*//' > "$OUTER_DIR/identity.md5" \
  || fail "$(lang de:"Fehler beim Erstellen der Identit&auml;t" en:"Erron on creating identity")"
cat << EOF > "$OUTER_DIR/contents.txt"
This file contains a settings backup by Freetz-NG
$fname
To restore with an older freetz revision: upload only settings.tgz
If you want to restore to another device, use: tools/decoder_for_settings_backup
EOF
[ -n "$SICPW" ] && echo 'For manual decryption: openssl enc -d -aes256 -in settings.tgz.crypted -out settings.tgz [-pbkdf2|-md sha256]' >> "$OUTER_DIR/contents.txt"
[ -s "$OUTER_DIR/contents.txt" ]  || fail "$(lang de:"Fehler beim Erstellen des Contents" en:"Erron on creating content")"

# Create temporary files of character streams in /var/flash
for x in /var/flash/*; do cat "$x" > "$INNER_DIR/${x##*/}"; done

# Pack (and encrypt) temporary settings file
if [ -z "$SICPW" ]; then
	tar cz -C "$OUTER_DIR" "${INNER_DIR##*/}/"                                                 > "$OUTER_DIR/settings.tgz" \
	  || fail "$(lang de:"Fehler beim Erzeugen der Datei" en:"Erron on creating file")"
else
	[ "$(openssl version | sed -rn 's/^OpenSSL ([0-9])\.([0-9])\..*/\1\2/p')" -lt 11 2>/dev/null ] && SSLOPT='-md sha256' || SSLOPT='-pbkdf2'
	tar cz -C "$OUTER_DIR" "${INNER_DIR##*/}/" | openssl enc -e -aes256 $SSLOPT -pass env:SICPW > "$OUTER_DIR/settings.tgz.crypted" \
	  || fail "$(lang de:"Fehler beim Verschl&uuml;sseln der Datei" en:"Erron on encrypting file")"
	# Add environment (to decode password strings)
	cat /proc/sys/urlader/environment          | openssl enc -e -aes256 $SSLOPT -pass env:SICPW > "$OUTER_DIR/environment.txt.crypted" \
	  || fail "$(lang de:"Fehler beim Verschl&uuml;sseln des Environments" en:"Erron on encrypting environment")"
fi
rm -rf "$INNER_DIR"

[ -s "$OUTER_DIR/settings.tgz.crypted" -o -s "$OUTER_DIR/settings.tgz" ] || fail "$(lang de:"Fehler beim Packen" en:"Error on packing")"
(
if [ -n "$FAIL" ]; then
	# Show error message
	. /usr/lib/libmodcgi.sh
	cgi --id=do_backup
	cgi_begin "$(lang de:"Konfiguration sichern (Backup)" en:"Backup configuration")"
	echo "<h1>$(lang de:"Fehler" en:"Error")</h1>"
	echo "<pre>$FAIL</pre>"
	echo "<p>"
	back_button --title="&nbsp;$(lang de:"Zur&uuml;ck" en:"Back")&nbsp;" mod backup
	echo "</p>"
	cgi_end
else
	# Create backup file
	CR=$'\r'
	echo "Content-Type: application/x-tar${CR}"
	echo "Content-Disposition: attachment; filename=\"$fname\"${CR}"
	echo "${CR}"
	tar c -C "${OUTER_DIR}" $(ls -1 $OUTER_DIR)
fi
) >&3
rm -rf "$OUTER_DIR"

