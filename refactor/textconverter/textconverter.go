package textconverter

import (
	"bufio"
	"bytes"
	"html"
	"io"
	"os"
	"strings"
)

// UnicodeFileToHTML converts a text file to an HTML string.
func UnicodeFileToHTML(fullFilenameWithPath string) (string, error) {
	file, err := os.Open(fullFilenameWithPath)
	if err != nil {
		return "", err
	}
	defer file.Close()

	var htmlBuilder strings.Builder
	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := scanner.Text()
		htmlBuilder.WriteString(html.EscapeString(line))
		htmlBuilder.WriteString("<br />")
	}

	if err := scanner.Err(); err != nil {
		return "", err
	}

	return htmlBuilder.String(), nil
}

// HTMLPagesConverter converts a file with page breaks into separate HTML pages.
type HTMLPagesConverter struct {
	Filename string
	breaks   []int64
}

// NewHTMLPagesConverter creates a new HTMLPagesConverter.
func NewHTMLPagesConverter(filename string) (*HTMLPagesConverter, error) {
	converter := &HTMLPagesConverter{
		Filename: filename,
		breaks:   []int64{0},
	}

	file, err := os.Open(filename)
	if err != nil {
		return nil, err
	}
	defer file.Close()

	reader := bufio.NewReader(file)
	var totalBytes int64

	for {
		line, err := reader.ReadString('\n')
		if err != nil && err != io.EOF {
			return nil, err
		}

		totalBytes += int64(len(line))

		if strings.Contains(line, "PAGE_BREAK") {
			converter.breaks = append(converter.breaks, totalBytes)
		}

		if err == io.EOF {
			break
		}
	}
	info, err := file.Stat()
	if err != nil {
		return nil, err
	}
	converter.breaks = append(converter.breaks, info.Size())

	return converter, nil
}

// GetHTMLPage returns the HTML for a specific page.
func (c *HTMLPagesConverter) GetHTMLPage(page int) (string, error) {
	if page < 0 || page+1 >= len(c.breaks) {
		return "", os.ErrNotExist
	}

	pageStart := c.breaks[page]
	pageEnd := c.breaks[page+1]

	file, err := os.Open(c.Filename)
	if err != nil {
		return "", err
	}
	defer file.Close()

	if _, err := file.Seek(pageStart, 0); err != nil {
		return "", err
	}

	reader := bufio.NewReader(io.LimitReader(file, pageEnd-pageStart))
	var htmlBuilder strings.Builder

	for {
		line, err := reader.ReadString('\n')
		if err != nil && err != io.EOF {
			return "", err
		}

		line = strings.TrimRight(line, "\r\n")
		if !strings.Contains(line, "PAGE_BREAK") {
			htmlBuilder.WriteString(html.EscapeString(line))
			htmlBuilder.WriteString("<br />")
		}

		if err == io.EOF {
			break
		}
	}

	return htmlBuilder.String(), nil
}
