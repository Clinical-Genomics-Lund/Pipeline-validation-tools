def parse_csv(csv) -> dict[str,str]:
    csv_content = dict()
    with open(csv) as in_fh:
        header = in_fh.readline().rstrip()
        content = in_fh.readline().rstrip()

        header_fields = header.split(',')
        content_fields = content.split(',')

        assert len(header_fields) == len(content_fields), f"Expected same nbr header_fields {len(header_fields)} and content_fields {len(content_fields)}"

        for i in range(0, len(header_fields)):
            header = header_fields[i]
            content = content_fields[i]
            csv_content[header] = content

    return csv_content
