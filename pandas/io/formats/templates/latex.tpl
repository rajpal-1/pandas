{% if table_wrapping %}
\begin{table}
{%- set position = parse_table(table_styles, 'position') %}
{%- if position is not none %}
[{{position}}]
{% endif %}
{% set float = parse_table(table_styles, 'float') %}
{% if float is not none%}
\{{float}}
{% endif %}
{% if caption %}
\caption{% raw %}{{% endraw %}{{caption}}{% raw %}}{% endraw %}

{% endif %}
{% for style in table_styles %}
{% if style['selector'] not in ['position', 'float', 'caption', 'toprule', 'midrule', 'bottomrule', 'column_format'] %}
\{{style['selector']}}{{parse_table(table_styles, style['selector'])}}
{% endif %}
{% endfor %}
{% endif %}
\begin{tabular}
{%- set column_format = parse_table(table_styles, 'column_format') %}
{%- if column_format is not none %}
{% raw %}{{% endraw %}{{column_format}}{% raw %}}{% endraw %}

{% else %}
{% raw %}{{% endraw %}{% for c in head[0] %}{% if c.is_visible != False %}l{% endif %}{% endfor %}{% raw %}}{% endraw %}

{% endif %}
{% set toprule = parse_table(table_styles, 'toprule') %}
{% if toprule is not none %}
\{{toprule}}
{% endif %}
{% for item in head[0] %}{%- if not loop.first %} & {% endif %}{{item.display_value}}{% endfor %} \\
{% set midrule = parse_table(table_styles, 'midrule') %}
{% if midrule is not none %}
\{{midrule}}
{% endif %}
{% for row in body %}
{% for c in row %}{% if not loop.first %} & {% endif %}{{parse_cell(c.cellstyle, c.display_value)}}{% endfor %} \\
{% endfor %}
{% set bottomrule = parse_table(table_styles, 'bottomrule') %}
{% if bottomrule is not none %}
\{{bottomrule}}
{% endif %}
\end{tabular}
{% if table_wrapping %}
\end{table}
{% endif %}
