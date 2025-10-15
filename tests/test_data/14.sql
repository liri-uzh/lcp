WITH RECURSIVE fixed_parts AS
  (SELECT "a"."article_id" AS "a",
          "a"."char_range" AS "a_char_range",
          "a"."pubdate" AS "a_pubdate",
          "s"."char_range" AS "s_char_range",
          "s"."segment_id" AS "s",
          "t1"."char_range" AS "t1_char_range",
          "t1"."token_id" AS "t1",
          "t1"."upos" AS "t1_upos",
          "t1_lemma"."lemma" AS "t1_lemma",
          "t2"."char_range" AS "t2_char_range",
          "t2"."token_id" AS "t2",
          "t2_lemma"."lemma" AS "t2_lemma"
   FROM
     (SELECT Segment_id
      FROM swissdox_3.fts_vector_derest vec
      WHERE vec.vector @@ '3ADJ <1> 2Schweiz') AS fts_vector_s
   CROSS JOIN "swissdox_3"."article_de" "a"
   CROSS JOIN "swissdox_3"."segment_derest" "s"
   CROSS JOIN "swissdox_3"."token_derest" "t1"
   CROSS JOIN "swissdox_3"."lemma_de" "t1_lemma"
   CROSS JOIN "swissdox_3"."token_derest" "t2"
   CROSS JOIN "swissdox_3"."lemma_de" "t2_lemma"
   WHERE "a"."char_range" && "s"."char_range"
     AND "fts_vector_s"."segment_id" = "s"."segment_id"
     AND "s"."segment_id" = "t1"."segment_id"
     AND ("t1"."upos")::text = ('ADJ')::text
     AND "s"."segment_id" = "t2"."segment_id"
     AND ("t2_lemma"."lemma")::text = ('Schweiz')::text
     AND "t1_lemma"."lemma_id" = "t1"."lemma_id"
     AND "t2"."token_id" - "t1"."token_id" = 1
     AND "t2_lemma"."lemma_id" = "t2"."lemma_id"
     AND (extract('year'
                  FROM ("a"."pubdate")::date))::numeric > (2020)::numeric ),
               gather AS
  (SELECT "a",
          "a_char_range",
          "a_pubdate",
          "s",
          "s_char_range",
          "t1",
          "t1_char_range",
          "t1_lemma",
          "t1_upos",
          "t2",
          "t2_char_range",
          "t2_lemma"
   FROM fixed_parts) ,
               match_list AS
  (SELECT gather."a" AS "a",
          gather."a_char_range" AS "a_char_range",
          gather."a_pubdate" AS "a_pubdate",
          gather."s" AS "s",
          gather."s_char_range" AS "s_char_range",
          gather."t1" AS "t1",
          gather."t1_char_range" AS "t1_char_range",
          gather."t1_lemma" AS "t1_lemma",
          gather."t1_upos" AS "t1_upos",
          gather."t2" AS "t2",
          gather."t2_char_range" AS "t2_char_range",
          gather."t2_lemma" AS "t2_lemma"
   FROM gather),
               res1 AS
  (SELECT DISTINCT 1::int2 AS rstype,
                   jsonb_build_array("s", jsonb_build_array("t1", "t2"))
   FROM match_list) ,
               res2 AS
  (SELECT 2::int2 AS rstype,
          jsonb_build_array(FALSE, "t1_lemma", frequency)
   FROM
     (SELECT "t1_lemma" ,
             count(*) AS frequency
      FROM match_list
      GROUP BY "t1_lemma") x) ,
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
FROM res2 ;
