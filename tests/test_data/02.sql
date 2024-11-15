WITH RECURSIVE fixed_parts AS
  (SELECT s.segment_id AS s,
          t1.token_id AS t1,
          t1_lemma.lemma AS t1_lemma,
          t2.token_id AS t2,
          t3.token_id AS t3
   FROM
     (SELECT Segment_id
      FROM sparcling1.fts_vector_enrest vec
      WHERE vec.vector @@ E'(!1a|1a) <1> (!1a|1a) <1> (!1a|1a)') AS fts_vector_s
   CROSS JOIN sparcling1.token_enrest t1
   CROSS JOIN sparcling1.session_en e
   CROSS JOIN sparcling1.session_alignment e_aligned
   CROSS JOIN sparcling1.segment_enrest s
   CROSS JOIN sparcling1.token_enrest t2
   CROSS JOIN sparcling1.token_enrest t3
   CROSS JOIN sparcling1.lemma_en t1_lemma
   WHERE (e_aligned.meta->>'date')::text ~ '^2000'
     AND e.alignment_id = e_aligned.alignment_id
     AND e.char_range && s.char_range
     AND fts_vector_s.segment_id = s.segment_id
     AND s.segment_id = t1.segment_id
     AND (t1.upos)::text = ('VERB')::text
     AND s.segment_id = t2.segment_id
     AND (t2.upos)::text = ('DET')::text
     AND s.segment_id = t3.segment_id
     AND ((t3.upos)::text = ('NOUN')::text
          AND (t3.xpos)::text = ('NP')::text)
     AND t1_lemma.lemma_id = t1.lemma_id
     AND t2.token_id - t1.token_id = 1
     AND t3.token_id - t2.token_id = 1 ),
               gather AS
  (SELECT s,
          t1,
          t1_lemma,
          t2,
          t3
   FROM fixed_parts) ,
               match_list AS
  (SELECT gather.s AS s,
          gather.t1 AS t1,
          gather.t1_lemma AS t1_lemma,
          gather.t2 AS t2,
          gather.t3 AS t3
   FROM gather),
               res0 AS
  (SELECT 0::int2 AS rstype,
          jsonb_build_array(count(*))
   FROM match_list) ,
               res1 AS
  (SELECT 1::int2 AS rstype,
          jsonb_build_array(s, jsonb_build_array(t1, t2, t3))
   FROM match_list) ,
               res2 AS
  (SELECT 2::int2 AS rstype,
          jsonb_build_array(t1_lemma, frequency)
   FROM
     (SELECT t1_lemma ,
             count(*) AS frequency
      FROM match_list
      GROUP BY t1_lemma) x)
SELECT *
FROM res0
UNION ALL
SELECT *
FROM res1
UNION ALL
SELECT *
FROM res2 ;
