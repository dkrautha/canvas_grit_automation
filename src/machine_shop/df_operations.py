# TODO: this file seems to be unused, I think I can just remove it?
import polars as pl


def update(
    self: pl.LazyFrame, df_other: pl.LazyFrame, join_columns: list[str]
) -> pl.LazyFrame:
    UPDATE_COLS = [c for c in df_other.columns if c not in join_columns]

    joined = self.join(df_other, how="left", on=join_columns, suffix="_NEW")
    update_new_vals = joined.with_columns(
        **{c: pl.coalesce([pl.col(c + "_NEW"), pl.col(c)]) for c in UPDATE_COLS}
    )
    drop_temp_cols = update_new_vals.select(pl.all().exclude("^.*_NEW$"))

    return drop_temp_cols


def extend_different_shape(df: pl.LazyFrame, df_other: pl.LazyFrame) -> pl.LazyFrame:
    columns = [c for c in df.columns if c not in df_other.columns]

    filled_in = df_other.with_columns(**{c: None for c in columns})

    columns = df.columns
    extended = pl.concat(
        [df.select(columns) for df in [df, filled_in]], how="vertical_relaxed"
    )

    return extended


def upsert(
    df: pl.LazyFrame, df_other: pl.LazyFrame, join_columns: list[str]
) -> pl.LazyFrame:
    KNOWN_SUFFIX = "_KNOWN"
    OLD_SUFFIX = "_IN_OLD"

    updated = update(df, df_other, join_columns)
    renamed_join_cols = updated.rename({c: c + KNOWN_SUFFIX for c in join_columns})
    checked_join_cols = df_other.with_context(renamed_join_cols).with_columns(
        [
            pl.col(c).is_in(pl.col(c + KNOWN_SUFFIX)).alias(c + OLD_SUFFIX)
            for c in join_columns
        ]
    )
    keep_only_unknown = checked_join_cols.filter(
        pl.fold(
            acc=pl.lit(True),
            function=lambda acc, c: acc & c,
            exprs=~pl.col(f"^.*{OLD_SUFFIX}$"),
        )
    )
    remove_added_cols = keep_only_unknown.drop(
        [c for c in updated.columns if c not in df_other.columns]
    )

    extended = extend_different_shape(updated, remove_added_cols).fill_null(False)
    return extended
