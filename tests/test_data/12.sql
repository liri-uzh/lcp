WITH RECURSIVE fixed_parts AS
  (SELECT "d"."char_range" AS "d_char_range",
          "d"."document_id" AS "d",
          "d"."meta"->>'classCode' AS "d_classCode",
          "s"."char_range" AS "s_char_range",
          "s"."segment_id" AS "s",
          "t3"."char_range" AS "t3_char_range",
          "t3"."segment_id" AS "t3_segment_id",
          "t3"."token_id" AS "t3",
          "t3"."xpos2" AS "t3_xpos2",

     (SELECT array_agg("tx"."form_id")
      FROM "bnc1"."tokenrest" "tx"
      WHERE "s"."segment_id" = "tx"."segment_id"
        AND ((lower("tx"."char_range"))::numeric < (lower("t3"."char_range") + 20)::numeric
             AND (lower("tx"."char_range"))::numeric > (lower("t3"."char_range") - 20)::numeric
             AND "tx"."token_id" != "t3"."token_id") ) AS "prox_form"
   FROM "bnc1".segmentrest AS s
   CROSS JOIN "bnc1"."document" "d"
   CROSS JOIN "bnc1"."tokenrest" "t3"
   WHERE "d"."char_range" && "s"."char_range"
     AND "s"."segment_id" = "t3"."segment_id"
     AND ("t3"."xpos2")::text = ('SUBST')::text
     AND ("d"."meta"->>'classCode')::text ~ '^S' ),
               match_list AS
  (SELECT fixed_parts."d" AS "d",
          fixed_parts."d_char_range" AS "d_char_range",
          fixed_parts."d_classCode" AS "d_classCode",
          fixed_parts."prox_form" AS "prox_form",
          fixed_parts."s" AS "s",
          fixed_parts."s_char_range" AS "s_char_range",
          fixed_parts."t3" AS "t3",
          fixed_parts."t3_char_range" AS "t3_char_range",
          fixed_parts."t3_segment_id" AS "t3_segment_id",
          fixed_parts."t3_xpos2" AS "t3_xpos2"
   FROM fixed_parts),
               res1 AS
  (SELECT DISTINCT 1::int2 AS rstype,
                   jsonb_build_array("s", jsonb_build_array("t3"))
   FROM match_list) ,
               collocates2 AS
  (SELECT "_token_collocate2"."form_id"
   FROM match_list
   CROSS JOIN "bnc1"."tokenrest" "_token_collocate2"
   WHERE "_token_collocate2"."token_id" <> match_list."t3"
     AND "_token_collocate2"."segment_id" = match_list."t3_segment_id"
     AND "_token_collocate2"."token_id" BETWEEN "t3" + (-2) AND "t3" + (2)),
               resXn2 AS
  (SELECT count(*) AS freq
   FROM collocates2),
               res2 AS
  (SELECT 2::int2 AS rstype,
          jsonb_build_array("collocates2_form", o, e)
   FROM
     (SELECT "collocates2_form"."form" AS "collocates2_form",
             o,
             1. * x.freq / token_n.freq * resXn2.freq AS e
      FROM
        (SELECT "collocates2"."form_id",
                freq,
                count(*) AS o
         FROM collocates2
         JOIN bnc1.token_freq USING ("form_id")
         WHERE token_freq.lemma_id IS NULL
           AND token_freq.xpos1 IS NULL
           AND token_freq.xpos2 IS NULL
         GROUP BY "form_id",
                  freq) x
      CROSS JOIN "bnc1"."form" "collocates2_form"
      CROSS JOIN bnc1.token_n
      CROSS JOIN resXn2
      WHERE "collocates2_form"."form_id" = x."form_id") x) ,
               collocates3 AS
  (SELECT unnest(match_list."prox_form") AS "form_id"
   FROM match_list),
               resXn3 AS
  (SELECT count(*) AS freq
   FROM collocates3),
               res3 AS
  (SELECT 3::int2 AS rstype,
          jsonb_build_array("collocates3_form", o, e)
   FROM
     (SELECT "collocates3_form"."form" AS "collocates3_form",
             o,
             1. * x.freq / token_n.freq * resXn3.freq AS e
      FROM
        (SELECT "collocates3"."form_id",
                freq,
                count(*) AS o
         FROM collocates3
         JOIN bnc1.token_freq USING ("form_id")
         WHERE token_freq.lemma_id IS NULL
           AND token_freq.xpos1 IS NULL
           AND token_freq.xpos2 IS NULL
         GROUP BY "form_id",
                  freq) x
      CROSS JOIN "bnc1"."form" "collocates3_form"
      CROSS JOIN bnc1.token_n
      CROSS JOIN resXn3
      WHERE "collocates3_form"."form_id" = x."form_id") x) ,
               res0 AS
  (SELECT 0::int2 AS rstype,
          jsonb_build_array(count(match_list.*))
   FROM match_list)
SELECT *
FROM res0
UNION ALL
SELECT *
FROM res1
UNION ALL
SELECT *
FROM res2
UNION ALL
SELECT *
FROM res3 ;
