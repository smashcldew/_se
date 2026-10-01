package main

import (
	"crypto/tls"
	"encoding/base64"
	"fmt"
	"io"
	"net/http"
	"net/http/cookiejar"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/spf13/pflag"
)

// 支援多次傳入的參數類別 (-H, -b)
type stringArray []string

func (i *stringArray) String() string {
	return strings.Join(*i, ", ")
}

func (i *stringArray) Set(value string) error {
	*i = append(*i, value)
	return nil
}

func (i *stringArray) Type() string {
	return "string"
}

// 帶有進度條的 Reader 封裝
type ProgressReader struct {
	reader       io.Reader
	total        int64
	current      int64
	showProgress bool
	urlStr       string
}

func (pr *ProgressReader) Read(p []byte) (int, error) {
	n, err := pr.reader.Read(p)
	pr.current += int64(n)
	if pr.showProgress && pr.total > 0 {
		percent := float64(pr.current) / float64(pr.total) * 100
		fmt.Fprintf(os.Stderr, "\r[%s] 下載進度: %.1f%% (%d/%d bytes)", pr.urlStr, percent, pr.current, pr.total)
		if pr.current >= pr.total {
			fmt.Fprintln(os.Stderr)
		}
	}
	return n, err
}

func main() {
	var (
		method     string
		headers    stringArray
		data       string
		output     string
		verbose    bool
		location   bool
		maxTime    int
		authUser   string
		noProgress bool
		cookies    stringArray
		insecure   bool
	)

	// 定義參數選項
	pflag.StringVarP(&method, "request", "X", "GET", "HTTP 方法，預設 GET")
	pflag.VarP(&headers, "header", "H", "自訂 header (NAME:VALUE，可重複)")
	pflag.StringVarP(&data, "data", "d", "", "請求 body (字串或 @filename)")
	pflag.StringVarP(&output, "output", "o", "", "body 寫入檔案 (多個 URL 時自動存成不同檔名)")
	pflag.BoolVarP(&verbose, "verbose", "v", false, "詳細輸出")
	pflag.BoolVarP(&location, "location", "L", false, "追蹤 redirect")
	pflag.IntVarP(&maxTime, "max-time", "m", 30, "timeout (秒)")
	pflag.StringVar(&authUser, "user", "", "user:password Basic Auth")
	pflag.BoolVar(&noProgress, "no-progress", false, "停用進度條")
	pflag.VarP(&cookies, "cookie", "b", "自訂 Cookie (NAME=VALUE，可重複)")
	pflag.BoolVarP(&insecure, "insecure", "k", false, "忽略 SSL 憑證驗證")

	pflag.CommandLine.SortFlags = false
	pflag.Usage = func() {
		fmt.Fprintf(os.Stderr, "用法: %s [選項] <URL1> <URL2> ...\n\n選項:\n", os.Args[0])
		pflag.PrintDefaults()
	}

	pflag.Parse()

	urls := pflag.Args()
	if len(urls) == 0 {
		fmt.Fprintln(os.Stderr, "錯誤: 未指定目標 URL")
		pflag.Usage()
		os.Exit(1)
	}

	// 處理 -d 帶入的資料（若為 @filename 則讀取檔案內容）
	var bodyBytes []byte
	if data != "" {
		if strings.HasPrefix(data, "@") {
			filePath := strings.TrimPrefix(data, "@")
			content, err := os.ReadFile(filePath)
			if err != nil {
				fmt.Fprintf(os.Stderr, "錯誤: 無法讀取檔案 %s: %v\n", filePath, err)
				os.Exit(1)
			}
			bodyBytes = content
		} else {
			bodyBytes = []byte(data)
		}
	}

	// 多 URL 併發處理
	var wg sync.WaitGroup
	for i, rawURL := range urls {
		wg.Add(1)
		go func(index int, targetURL string) {
			defer wg.Done()
			executeRequest(targetURL, index, len(urls), method, headers, bodyBytes, output, verbose, location, maxTime, authUser, noProgress, cookies, insecure)
		}(i, rawURL)
	}
	wg.Wait()

}

func executeRequest(
	targetURL string,
	index int,
	totalURLs int,
	method string,
	headers []string,
	bodyBytes []byte,
	output string,
	verbose bool,
	location bool,
	maxTime int,
	authUser string,
	noProgress bool,
	cookies []string,
	insecure bool,
) {
	jar, _ := cookiejar.New(nil)

	transport := &http.Transport{
		TLSClientConfig: &tls.Config{InsecureSkipVerify: insecure},
	}

	client := &http.Client{
		Transport: transport,
		Timeout:   time.Duration(maxTime) * time.Second,
	}

	// 不跟隨 Redirect 時停在 301/302
	if !location {
		client.CheckRedirect = func(req *http.Request, via []*http.Request) error {
			return http.ErrUseLastResponse
		}
	}

	// 處理 Cookies
	if len(cookies) > 0 {
		u, err := url.Parse(targetURL)
		if err == nil {
			var cookieList []*http.Cookie
			for _, c := range cookies {
				parts := strings.SplitN(c, "=", 2)
				if len(parts) == 2 {
					cookieList = append(cookieList, &http.Cookie{
						Name:  strings.TrimSpace(parts[0]),
						Value: strings.TrimSpace(parts[1]),
						Path:  "/",
					})
				}
			}
			jar.SetCookies(u, cookieList)
		}
		client.Jar = jar
	}

	var bodyReader io.Reader
	if len(bodyBytes) > 0 {
		bodyReader = strings.NewReader(string(bodyBytes))
	}

	req, err := http.NewRequest(strings.ToUpper(method), targetURL, bodyReader)
	if err != nil {
		fmt.Fprintf(os.Stderr, "[%s] 建立請求失敗: %v\n", targetURL, err)
		return
	}

	req.Header.Set("User-Agent", "MiniCurl/2.0")

	// 帶入 Headers
	for _, h := range headers {
		parts := strings.SplitN(h, ":", 2)
		if len(parts) == 2 {
			req.Header.Set(strings.TrimSpace(parts[0]), strings.TrimSpace(parts[1]))
		}
	}

	// Basic Auth
	if authUser != "" {
		auth := base64.StdEncoding.EncodeToString([]byte(authUser))
		req.Header.Set("Authorization", "Basic "+auth)
	}

	// -v 輸出標頭
	if verbose {
		fmt.Fprintf(os.Stderr, "> %s %s %s\n", req.Method, req.URL.Path, req.Proto)
		fmt.Fprintf(os.Stderr, "> Host: %s\n", req.URL.Host)
		for k, v := range req.Header {
			fmt.Fprintf(os.Stderr, "> %s: %s\n", k, strings.Join(v, ", "))
		}
		fmt.Fprintln(os.Stderr, "> ")
	}

	resp, err := client.Do(req)
	if err != nil {
		fmt.Fprintf(os.Stderr, "[%s] 請求發送失敗: %v\n", targetURL, err)
		return
	}
	defer resp.Body.Close()

	if verbose {
		fmt.Fprintf(os.Stderr, "< %s %s\n", resp.Proto, resp.Status)
		for k, v := range resp.Header {
			fmt.Fprintf(os.Stderr, "< %s: %s\n", k, strings.Join(v, ", "))
		}
		fmt.Fprintln(os.Stderr, "< ")
	}

	var writer io.Writer = os.Stdout

	// 輸出至檔案
	if output != "" {
		outPath := output
		if totalURLs > 1 {
			ext := filepath.Ext(output)
			base := strings.TrimSuffix(output, ext)
			outPath = fmt.Sprintf("%s_%d%s", base, index+1, ext)
		}
		f, err := os.Create(outPath)
		if err != nil {
			fmt.Fprintf(os.Stderr, "[%s] 無法建立輸出檔案 %s: %v\n", targetURL, outPath, err)
			return
		}
		defer f.Close()
		writer = f
	}

	// 進度條顯示
	var srcReader io.Reader = resp.Body
	if !noProgress && output != "" {
		srcReader = &ProgressReader{
			reader:       resp.Body,
			total:        resp.ContentLength,
			showProgress: true,
			urlStr:       targetURL,
		}
	}

	_, err = io.Copy(writer, srcReader)
	if err != nil {
		fmt.Fprintf(os.Stderr, "[%s] 讀取 Response 失敗: %v\n", targetURL, err)
	}
}
