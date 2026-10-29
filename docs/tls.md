# TLS deployment and trust rotation

These conclusions come from controlled tests completed October 29, 2026 on one
HT801 V1.1A running 1.0.65.3. They are not HT814 test results or a guarantee for
other firmware. No production hardening baseline was applied by that investigation.

| Client | Chain validation | Server identity | Trust source |
| --- | --- | --- | --- |
| HTTPS/FTPS provisioning | P8463 | P22030 | P8502 |
| SIP TLS | P2367 | P2311 | P8502 |
| TR-069 ACS | Enforced in tested cases even with P8463=0 | Enforced even with P22030=0 | P8502 |
| TLS syslog | Global validation affected it | Wrong name rejected under strict settings; hostname switch alone not conclusively isolated | Built-in-only rejected test CA; custom-only accepted it |

`P8502` selects built-in roots (0), custom roots (1), or both (2).

SIP needs its own account checks: global HTTPS verification did not substitute for
them. SIP rejected an IP-SAN-only certificate with domain checking enabled but
accepted a matching DNS SAN. Use a DNS hostname and matching DNS SANs.
OpenVPN has a separate configuration namespace. Optional XMPP and other untested
clients have no inferred policy here. Use exact firmware templates for HT814's
account/profile parameters rather than copying HT801 account IDs.

## Root bundles and limits

HTTPS provisioning, SIP, and ACS each accepted all three roots in a roughly 3.4 KB
PEM bundle in CA A after reboot, and rejected an unknown issuer under the same
configuration. This establishes a useful small bundle, not a maximum size/count,
CA B capacity, or support for an entire browser root store. Live replacement was
unreliable; some new roots worked only after reboot. Intermediate-only anchors,
leaf pinning, and bundled CRLs were not established as deployable formats.

Use reviewed SHA-256 root selections in `profiles.<name>.roots` (or a device's
replacement `roots` mapping). A string selects one root; an ordered array makes a
PEM bundle. A device mapping replaces the entire profile mapping, not individual
slots. The renderer accepts only slots `a` and `b`, rejects empty bundles and
repeated fingerprints within a slot, verifies content fingerprints and current
certificate validity with OpenSSL, and reads only the current downloaded inventory.
This does not establish how the ATA itself handles expired trust anchors.

Omitting a P-value retains device state. Removing a selection, dropping a template
element, or rendering an empty CA field must never be interpreted as deleting trust.
CA fields are write-only: known-present content read back blank. A blank submission
still trusted the previous test root after reboot. The investigation ultimately
replaced the test bundle with an expired unused placeholder and demonstrated that
previously accepted chains no longer reached application traffic. This is cleanup
evidence, not a general recipe for production trust deletion. Plan rotations as
explicit full replacements of each previously used slot, with behavioral verification.

## Revocation and vendor trust

HTTPS, FTPS, SIP, ACS, and TLS syslog accepted otherwise-valid revoked test leaves
without looking up their reachable advertised CRL/OCSP resources. Fixed post-reboot
HTTPS, SIP, and ACS tests also accepted revoked intermediates. Ordinary chain and
name verification is therefore not a demonstrated revocation control. Bundled-CRL
support was not established. A separate vendor blocklist was not ruled out.

Deleting a cached intermediate cannot block a server from supplying it again under
a trusted root. Respond to compromised CA paths by reviewing/removing their root
anchors or changing providers/trust paths as appropriate. A routine Mozilla refresh
cannot make unchanged ATA configurations stop trusting a root. If a selected root
vanishes upstream, rendering deliberately fails and the last published XML remains;
alert, review a replacement trust set, render, and verify rollout on every device.
Mozilla browser-specific distrust mechanisms and constraints are not fully expressed
in the PEM inventory. No claim is made about affected roots in the built-in store,
whose complete inventory could not be recovered.

One recovered Grandstream factory VPN CA used a 1024-bit RSA key and authenticated
the observed GDMS ACS chain. OpenSSL authentication level 2 rejected that weak key.
It was not evidence of the complete built-in inventory. Mozilla public roots alone
must not be assumed sufficient for GDMS. This service does not auto-import recovered
vendor certificates or weaken OpenSSL policy to accept them. Decide whether GDMS is
needed before choosing custom-only trust. Disabling GDMS and migrating away from its
legacy PKI are explicit operator decisions, not template defaults. Combined mode
retains built-ins; it does not remove questionable factory roots.

## Staged deployment

1. Keep a tested local management recovery path and private backups. Reconcile GDMS,
   DHCP provisioning overrides, and other management sources; cloud reconnection can
   reapply credentials/settings. This service does not modify devices itself.
2. Establish reliable DNS and time. The tested adapter repeatedly booted with a
   future clock despite verified NTP sources. Manual synchronization corrected it
   temporarily, not persistently. Do not use short certificate windows or silence
   alone as evidence of correct trust. NTP settings are not a proven fix here.
3. Install the selected roots through an already authenticated provisioning path or
   a deliberately isolated bootstrap. The default sample does not configure TLS;
   the optional `ht801-tls.xml` template is a staged strict profile and needs all
   its variables and a reviewed CA A selection before rendering. It sets SIP TLS,
   global and SIP checks, and custom-only trust. Its provisioning endpoint must be
   reachable with a certificate under the installed roots. Include every required
   service's roots before switching to custom-only. Do not reuse this profile on
   HT814 without independent validation.
4. Render, trigger provisioning, then reboot the test unit after a trust change.
   SSH `commit` saves flash; Apply and stored values alone do not prove active trust.
   Wait for web/telephony services to settle, not merely SSH availability.
5. Verify the clock, successful real client operations with each required trust path,
   and rejection of an otherwise-matching unknown issuer. When rotating out roots,
   test that chains under the old roots are rejected too. A TLS handshake alone or
   a blank certificate readback is not sufficient evidence. Check provisioning,
   SIP, and ACS separately where used, before advancing to other sites.

The renderer publishes files atomically on the server. It does not establish fleet
convergence, manage reboots, prove device-side removal, or provide online revocation.

Official parameter references: [HT80x administration](https://documentation.grandstream.com/knowledge-base/ht80x-administration-guide/),
[Grandstream firmware configuration templates](https://www.grandstream.com/support/tools),
and [Mozilla PEM extraction limitations](https://curl.se/docs/caextract.html).
