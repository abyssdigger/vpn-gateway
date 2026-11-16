# Disposition — NG1 production configuration resolution review

F1 and F2 were accepted and incorporated before implementation.

The proposal is approved for promotion into NG1 Draft 5. The implementation will:

- require router and instance schema_version=1;
- make enabled Device NAT explicit (none|masquerade);
- adopt Device publication mapping syntax;
- adopt ordered traffic-envelope rules with RETURN-based allow semantics;
- enforce external publication collisions and cross-Device internal ownership;
- use the safe opaque instance-ID grammar.

The previous NAT and bootstrap syntax blockers are resolved by this design. Publication
and traffic-envelope syntax are also no longer open after Draft 5 promotion.
