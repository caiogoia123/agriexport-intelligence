-- Staging: rename, type and standardize Comex Stat exports. One model per source.
-- Phase 2: replace the placeholder select with real source columns.

with source as (
    select * from {{ source('raw', 'comexstat_exports') }}
),

renamed as (
    select
        -- keys / dimensions
        cast(ref_date as date)          as ref_date,
        cast(ncm_code as string)        as ncm_code,
        cast(country_code as string)    as destination_country_code,
        cast(state_code as string)      as origin_state_code,

        -- measures
        cast(fob_usd as numeric)        as fob_usd,
        cast(net_weight_kg as numeric)  as net_weight_kg
    from source
)

select * from renamed
