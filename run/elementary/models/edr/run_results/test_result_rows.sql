
      
        
            delete from "postgres"."elementary"."test_result_rows"
            where (
                elementary_test_results_id) in (
                select (elementary_test_results_id)
                from "test_result_rows__dbt_tmp121324290128"
            );

        
    

    insert into "postgres"."elementary"."test_result_rows" ("elementary_test_results_id", "result_row", "detected_at", "created_at")
    (
        select "elementary_test_results_id", "result_row", "detected_at", "created_at"
        from "test_result_rows__dbt_tmp121324290128"
    )
  