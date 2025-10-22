WITH RECURSIVE fixed_parts AS
  (SELECT "ca"."char_range" AS "ca_char_range",
          "ca"."token_id" AS "ca",
          "ca_form"."form" AS "ca_form",
          "jouer"."char_range" AS "jouer_char_range",
          "jouer"."token_id" AS "jouer",
          "jouer_lemma"."lemma" AS "jouer_lemma",
          "s"."char_range" AS "s_char_range",
          "s"."segment_id" AS "s"
   FROM
     (SELECT Segment_id
      FROM sparcling1.fts_vector_frrest vec
      WHERE vec.vector @@ '(1cela | 1ça)'
        AND vec.vector @@ '2jouer') AS fts_vector_s
   CROSS JOIN "sparcling1"."segment_frrest" "s"
   CROSS JOIN "sparcling1"."token_frrest" "ca"
   CROSS JOIN "sparcling1"."form_fr" "ca_form"
   CROSS JOIN "sparcling1"."token_frrest" "jouer"
   CROSS JOIN "sparcling1"."lemma_fr" "jouer_lemma"
   CROSS JOIN "sparcling1"."deprel_fr" "anonymous3"
   WHERE "ca_form"."form_id" = "ca"."form_id"
     AND "fts_vector_s"."segment_id" = "s"."segment_id"
     AND "jouer"."token_id" - "ca"."token_id" > 0
     AND "jouer_lemma"."lemma_id" = "jouer"."lemma_id"
     AND "s"."segment_id" = "ca"."segment_id"
     AND (("ca_form"."form")::text = ('cela')::text
          OR ("ca_form"."form")::text = ('ça')::text)
     AND "s"."segment_id" = "jouer"."segment_id"
     AND (("anonymous3"."dependent" = "ca"."token_id"
           AND "anonymous3"."head" = "jouer"."token_id")
          AND ("jouer_lemma"."lemma")::text = ('jouer')::text)
     AND ("jouer"."token_id" - "ca"."token_id" - 1) % 1 = 0
     AND (TRUE) = ALL
       (SELECT "s"."segment_id" = "s0_t0"."segment_id"
        FROM sparcling1.token_frrest s0_t0
        WHERE s0_t0.token_id > ca.token_id
          AND (s0_t0.token_id - ca.token_id - 1) % 1 = 0
          AND s0_t0.token_id < jouer.token_id
          AND s0_t0.segment_id = s.segment_id ) ),
               gather AS
  (SELECT "ca",
          "ca_char_range",
          "ca_form",
          "jouer",
          "jouer_char_range",
          "jouer_lemma",
          "s",
          "s_char_range",
          fixed_parts.ca AS min_seq,
          fixed_parts.jouer AS max_seq
   FROM fixed_parts) ,
               match_list AS
  (SELECT ARRAY
     (SELECT "t"."token_id"
      FROM "sparcling1"."token_frrest" "t"
      WHERE "t"."segment_id" = gather."s"
        AND "t"."token_id" BETWEEN gather."min_seq"::bigint AND gather."max_seq"::bigint) AS "seq",
          gather."ca" AS "ca",
          gather."ca_char_range" AS "ca_char_range",
          gather."ca_form" AS "ca_form",
          gather."jouer" AS "jouer",
          gather."jouer_char_range" AS "jouer_char_range",
          gather."jouer_lemma" AS "jouer_lemma",
          gather."s" AS "s",
          gather."s_char_range" AS "s_char_range"
   FROM gather),
               res1 AS
  (SELECT DISTINCT 1::int2 AS rstype,
                   jsonb_build_array("s", jsonb_build_array("seq"))
   FROM match_list) ,
               res0 AS
  (SELECT 0::int2 AS rstype,
          jsonb_build_array(count(match_list.*))
   FROM match_list)
SELECT *
FROM res0
UNION ALL
SELECT *
FROM res1 ;