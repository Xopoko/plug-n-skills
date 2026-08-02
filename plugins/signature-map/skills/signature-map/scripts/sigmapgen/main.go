package main

import (
	"bufio"
	"crypto/sha1"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"io/fs"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"
	"unicode"
)

type Entry struct {
	Path      string `json:"path"`
	Signature string `json:"signature"`
	Comment   string `json:"comment"`
	Line      int    `json:"line"`
	Kind      string `json:"kind"`
}

type FileMeta struct {
	Size       int64 `json:"size"`
	MtimeNs    int64 `json:"mtime_ns"`
	EntryCount int   `json:"entry_count"`
}

type GitState struct {
	Head  string `json:"head"`
	Clean bool   `json:"clean"`
}

type Meta struct {
	Version     int                 `json:"version"`
	Root        string              `json:"root"`
	GeneratedAt int64               `json:"generated_at"`
	Git         *GitState           `json:"git,omitempty"`
	Files       map[string]FileMeta `json:"files"`
	SourceMode  string              `json:"source_mode"`
}

type Candidate struct {
	RelPath string
	AbsPath string
	Lang    string
	Size    int64
	MtimeNs int64
}

type Decl struct {
	Idx  int
	Name string
	Sig  string
	Kind string
}

type FileProfile struct {
	Path       string  `json:"path"`
	Lang       string  `json:"lang"`
	SizeBytes  int64   `json:"size_bytes"`
	Lines      int     `json:"lines"`
	Entries    int     `json:"entries"`
	ReadSec    float64 `json:"read_sec"`
	ParseSec   float64 `json:"parse_sec"`
	CommentSec float64 `json:"comment_sec"`
	BuildSec   float64 `json:"build_sec"`
	TotalSec   float64 `json:"total_sec"`
}

type parseResult struct {
	Task    Candidate
	Entries []Entry
	Profile FileProfile
}

type Config struct {
	IndexHashedBundles bool
	DisableComments    bool
	MaxParseLineLen    int
	MaxSignatureLines  int
	Workers            int
	Profile            bool
	ProfileTop         int
	CacheDir           string
}

var (
	swiftFuncNameRe = regexp.MustCompile(`\bfunc\b\s*([^\s(<]+)`)
	swiftTypeRe     = regexp.MustCompile(`^\s*(?:@[\w().,\s]+\s+)*(?:public|private|fileprivate|internal|open|final|indirect|actor|nonisolated|static|class|mutating|nonmutating|lazy|required|convenience|override|weak|unowned|\s+)*\b(class|struct|enum|protocol|actor|typealias|extension)\b\s+([A-Za-z_][A-Za-z0-9_]*)`)
	swiftCallableRe = regexp.MustCompile(`^\s*(?:@[\w().,\s]+\s+)*(?:public|private|fileprivate|internal|open|final|indirect|actor|nonisolated|static|class|mutating|nonmutating|lazy|required|convenience|override|weak|unowned|\s+)*(func|init[!?]?|deinit|subscript)\b`)

	objcMethodStartRe = regexp.MustCompile(`^\s*[-+]\s*\(`)
	objcTypeRe        = regexp.MustCompile(`^\s*@(?:interface|protocol|implementation)\s+([A-Za-z_][A-Za-z0-9_]*)`)

	pyDefRe   = regexp.MustCompile(`^\s*(?:async\s+def|def)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(`)
	pyClassRe = regexp.MustCompile(`^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:\(|:)`)

	rbDefRe = regexp.MustCompile(`^\s*def\s+([A-Za-z0-9_.!?=]+)`)

	jsFuncDeclRe          = regexp.MustCompile(`^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+([A-Za-z0-9_$]+)\s*\(`)
	jsFuncExprRe          = regexp.MustCompile(`^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z0-9_$]+)\s*=\s*(?:async\s+)?function\b`)
	jsArrowRe             = regexp.MustCompile(`^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z0-9_$]+)\s*=\s*(?:async\s+)?(?:\([^=]*\)|[A-Za-z0-9_$]+)\s*=>`)
	jsClassMethodInlineRe = regexp.MustCompile(`^\s*(?:async\s+)?(?:static\s+)?(?:get\s+|set\s+)?([A-Za-z0-9_$]+)\s*\([^)]*\)\s*\{`)
	jsTypeRe              = regexp.MustCompile(`^\s*(?:export\s+)?(?:default\s+)?\b(class|interface|type|enum)\b\s+([A-Za-z_][A-Za-z0-9_]*)`)

	ktFunRe  = regexp.MustCompile(`^\s*(?:@[\w.]+\s+)*(?:public|private|protected|internal|final|open|override|inline|suspend|tailrec|operator|infix|external|abstract|companion|static|\s+)*\s*fun\s+([A-Za-z0-9_<>]+)\s*\(`)
	ktTypeRe = regexp.MustCompile(`^\s*(?:@[\w.]+\s+)*(?:public|private|protected|internal|sealed|data|open|abstract|final|enum|annotation|value|inner|companion|\s+)*\s*(class|interface|enum\s+class|object|typealias)\s+([A-Za-z_][A-Za-z0-9_]*)`)

	javaMethodRe = regexp.MustCompile(`^\s*(?:@[\w.]+\s+)*(?:public|private|protected|static|final|synchronized|abstract|native|strictfp|\s+)*\s*[\w<>\[\],\s]+\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(`)
	javaTypeRe   = regexp.MustCompile(`^\s*(?:@[\w.]+\s+)*(?:public|private|protected|abstract|final|static|sealed|non-sealed|\s+)*\s*(class|interface|enum|record)\s+([A-Za-z_][A-Za-z0-9_]*)`)

	shFuncRe = regexp.MustCompile(`^\s*(?:function\s+)?([A-Za-z0-9_]+)\s*\(\)\s*(?:\{|$)`)

	cFuncRe    = regexp.MustCompile(`^\s*([A-Za-z_][A-Za-z0-9_\s\*\&:<>,\[\]]+?)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(`)
	cTypeRe    = regexp.MustCompile(`^\s*(?:typedef\s+)?(struct|class|enum)\s+([A-Za-z_][A-Za-z0-9_]*)`)
	cTypedefRe = regexp.MustCompile(`^\s*typedef\s+.*?\b([A-Za-z_][A-Za-z0-9_]*)\s*;`)

	decoratorRe    = regexp.MustCompile(`^\s*@`)
	preprocessorRe = regexp.MustCompile(`^\s*#(?:if|elseif|else|endif|define|undef|pragma|warning|error)\b`)
	hashedAssetRe  = regexp.MustCompile(`\.[0-9a-f]{7,}\.`)
)

var (
	allowedExt = map[string]bool{
		".swift": true, ".m": true, ".mm": true, ".h": true,
		".c": true, ".cc": true, ".cpp": true, ".hpp": true,
		".js": true, ".jsx": true, ".ts": true, ".tsx": true,
		".py": true, ".rb": true, ".sh": true, ".bash": true, ".zsh": true,
		".kt": true, ".kts": true, ".java": true, ".groovy": true,
	}
	langByExt = map[string]string{
		".swift":  "swift",
		".m":      "objc",
		".mm":     "objc",
		".h":      "objc",
		".c":      "c",
		".cc":     "cpp",
		".cpp":    "cpp",
		".hpp":    "cpp",
		".js":     "js",
		".jsx":    "js",
		".ts":     "ts",
		".tsx":    "ts",
		".py":     "py",
		".rb":     "rb",
		".sh":     "sh",
		".bash":   "sh",
		".zsh":    "sh",
		".kt":     "kt",
		".kts":    "kt",
		".java":   "java",
		".groovy": "java",
	}
	excludeDirLower = map[string]bool{
		".git": true, ".github": true, ".swiftpm": true, ".build": true,
		"build": true, "deriveddata": true, "carthage": true, "pods": true,
		"remotedependencies": true, "node_modules": true,
		".idea": true, ".vscode": true,
	}
	excludeDirSuffixes = []string{".xcworkspace", ".xcodeproj"}
	hashCommentLang = map[string]bool{"py": true, "rb": true, "sh": true}
	cLikeLang       = map[string]bool{"swift": true, "objc": true, "c": true, "cpp": true, "js": true, "ts": true, "kt": true, "java": true}
)

func main() {
	rootArg := flag.String("root", "", "repository root")
	outArg := flag.String("out", "", "output path")
	flag.Parse()

	root := strings.TrimSpace(*rootArg)
	if root == "" {
		if r, err := detectRootFromCwd(); err == nil {
			root = r
		} else {
			cwd, _ := os.Getwd()
			root = cwd
		}
	}
	absRoot, err := filepath.Abs(root)
	if err != nil {
		fmt.Fprintf(os.Stderr, "ERROR: failed to resolve root: %v\n", err)
		os.Exit(2)
	}
	st, err := os.Stat(absRoot)
	if err != nil || !st.IsDir() {
		fmt.Fprintf(os.Stderr, "ERROR: root directory does not exist: %s\n", absRoot)
		os.Exit(2)
	}

	out := strings.TrimSpace(*outArg)
	if out == "" {
		out = filepath.Join(absRoot, "signatures.json")
	} else if !filepath.IsAbs(out) {
		out = filepath.Join(absRoot, out)
	}

	cfg := loadConfig(absRoot)
	if err := run(absRoot, out, cfg); err != nil {
		fmt.Fprintf(os.Stderr, "ERROR: %v\n", err)
		os.Exit(1)
	}
}

func defaultCacheDir() string {
	if xdg := strings.TrimSpace(os.Getenv("XDG_CACHE_HOME")); xdg != "" {
		return filepath.Join(xdg, "signature-map")
	}
	home, err := os.UserHomeDir()
	if err != nil || strings.TrimSpace(home) == "" {
		return ""
	}
	return filepath.Join(home, ".cache", "signature-map")
}

func loadConfig(root string) Config {
	workers := envInt("SIGMAP_WORKERS", minInt(12, maxInt(1, runtime.NumCPU())))
	if workers < 1 {
		workers = 1
	}
	cfg := Config{
		IndexHashedBundles: envBool("SIGMAP_INDEX_HASHED_BUNDLES", false),
		DisableComments:    envBool("SIGMAP_DISABLE_COMMENTS", false),
		MaxParseLineLen:    envInt("SIGMAP_MAX_LINE_LENGTH", 2000),
		MaxSignatureLines:  envInt("SIGMAP_MAX_SIGNATURE_LINES", 12),
		Workers:            workers,
		Profile:            envBool("SIGMAP_PROFILE", false),
		ProfileTop:         envInt("SIGMAP_PROFILE_TOP", 20),
		CacheDir:           envString("SIGMAP_CACHE_DIR", defaultCacheDir()),
	}
	if cfg.MaxParseLineLen < 80 {
		cfg.MaxParseLineLen = 80
	}
	if cfg.MaxSignatureLines < 2 {
		cfg.MaxSignatureLines = 2
	}
	if cfg.ProfileTop < 1 {
		cfg.ProfileTop = 20
	}
	if cfg.CacheDir == "" {
		cfg.CacheDir = filepath.Join(root, ".sigmap-cache")
	}
	return cfg
}

func run(root, out string, cfg Config) error {
	started := time.Now()
	if err := os.MkdirAll(filepath.Dir(out), 0o755); err != nil {
		return fmt.Errorf("mkdir output dir: %w", err)
	}
	if err := os.MkdirAll(cfg.CacheDir, 0o755); err != nil {
		return fmt.Errorf("mkdir cache dir: %w", err)
	}

	metaPath := metaPathForRoot(root, cfg.CacheDir)
	meta, _ := loadMeta(metaPath)
	if meta == nil {
		meta = &Meta{Version: 1, Root: root, Files: map[string]FileMeta{}}
	}

	currentGit := gitState(root, out)
	if canFastSkip(root, out, meta, currentGit) {
		dt := time.Since(started).Seconds()
		head := ""
		if currentGit != nil {
			head = currentGit.Head
		}
		if len(head) > 12 {
			head = head[:12]
		}
		fmt.Printf("No source changes detected (HEAD %s clean). Kept existing map: %s (%.2fs)\n", head, out, dt)
		return nil
	}

	candidates, sourceMode, err := collectCandidates(root, cfg)
	if err != nil {
		return err
	}
	collectDone := time.Now()

	prevFiles := meta.Files
	if prevFiles == nil {
		prevFiles = map[string]FileMeta{}
	}

	toParse := make([]Candidate, 0, len(candidates))
	unchanged := make([]Candidate, 0, len(candidates))
	for _, c := range candidates {
		if pf, ok := prevFiles[c.RelPath]; ok && pf.Size == c.Size && pf.MtimeNs == c.MtimeNs {
			unchanged = append(unchanged, c)
		} else {
			toParse = append(toParse, c)
		}
	}

	prevByFile := map[string][]Entry{}
	if len(unchanged) > 0 {
		if prevEntries, err := loadEntries(out); err == nil {
			for _, e := range prevEntries {
				if idx := strings.Index(e.Path, "::"); idx > 0 {
					rel := e.Path[:idx]
					prevByFile[rel] = append(prevByFile[rel], e)
				}
			}
		}
	}

	entries := make([]Entry, 0, 32768)
	newFilesMeta := make(map[string]FileMeta, len(candidates))
	reusedFiles := 0
	for _, c := range unchanged {
		if prev, ok := prevByFile[c.RelPath]; ok {
			reusedFiles++
			entries = append(entries, prev...)
			newFilesMeta[c.RelPath] = FileMeta{Size: c.Size, MtimeNs: c.MtimeNs, EntryCount: len(prev)}
		} else {
			toParse = append(toParse, c)
		}
	}

	parsedByFile, profiles, err := parseCandidates(toParse, cfg)
	if err != nil {
		return err
	}
	for _, c := range toParse {
		fileEntries := parsedByFile[c.RelPath]
		entries = append(entries, fileEntries...)
		newFilesMeta[c.RelPath] = FileMeta{Size: c.Size, MtimeNs: c.MtimeNs, EntryCount: len(fileEntries)}
	}
	parseDone := time.Now()

	sort.Slice(entries, func(i, j int) bool {
		if entries[i].Path == entries[j].Path {
			return entries[i].Line < entries[j].Line
		}
		return entries[i].Path < entries[j].Path
	})

	if err := writeEntries(out, entries); err != nil {
		return err
	}
	dumpDone := time.Now()

	metaOut := &Meta{
		Version:     1,
		Root:        root,
		GeneratedAt: time.Now().Unix(),
		Git:         currentGit,
		Files:       newFilesMeta,
		SourceMode:  sourceMode,
	}
	if err := writeMeta(metaPath, metaOut); err != nil {
		return err
	}

	if cfg.Profile {
		printTopProfiles(profiles, cfg.ProfileTop)
	}

	collectSec := collectDone.Sub(started).Seconds()
	parseSec := parseDone.Sub(collectDone).Seconds()
	dumpSec := dumpDone.Sub(parseDone).Seconds()
	totalSec := time.Since(started).Seconds()
	fmt.Printf(
		"Wrote %d signatures to %s (files total=%d parsed=%d reused=%d via=%s collect=%.2fs parse=%.2fs dump=%.2fs total=%.2fs)\n",
		len(entries), out, len(candidates), len(toParse), reusedFiles, sourceMode, collectSec, parseSec, dumpSec, totalSec,
	)
	return nil
}

func canFastSkip(root, out string, meta *Meta, currentGit *GitState) bool {
	if meta == nil || currentGit == nil || meta.Git == nil {
		return false
	}
	if meta.Root != root {
		return false
	}
	if meta.Git.Head == "" || currentGit.Head == "" {
		return false
	}
	if meta.Git.Head != currentGit.Head {
		return false
	}
	if !meta.Git.Clean || !currentGit.Clean {
		return false
	}
	if st, err := os.Stat(out); err != nil || st.IsDir() {
		return false
	}
	return true
}

func parseCandidates(tasks []Candidate, cfg Config) (map[string][]Entry, []FileProfile, error) {
	result := make(map[string][]Entry, len(tasks))
	profiles := make([]FileProfile, 0, len(tasks))
	if len(tasks) == 0 {
		return result, profiles, nil
	}

	sort.Slice(tasks, func(i, j int) bool {
		if tasks[i].Size == tasks[j].Size {
			return tasks[i].RelPath < tasks[j].RelPath
		}
		return tasks[i].Size > tasks[j].Size
	})

	workers := minInt(cfg.Workers, len(tasks))
	if workers < 1 {
		workers = 1
	}

	jobs := make(chan Candidate)
	results := make(chan parseResult, len(tasks))
	var wg sync.WaitGroup
	for i := 0; i < workers; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for t := range jobs {
				results <- parseOneFile(t, cfg)
			}
		}()
	}

	go func() {
		for _, t := range tasks {
			jobs <- t
		}
		close(jobs)
		wg.Wait()
		close(results)
	}()

	for r := range results {
		result[r.Task.RelPath] = r.Entries
		profiles = append(profiles, r.Profile)
	}

	return result, profiles, nil
}

func parseOneFile(task Candidate, cfg Config) parseResult {
	profile := FileProfile{
		Path:      task.RelPath,
		Lang:      task.Lang,
		SizeBytes: task.Size,
	}
	started := time.Now()
	readStarted := time.Now()
	data, err := os.ReadFile(task.AbsPath)
	profile.ReadSec = time.Since(readStarted).Seconds()
	if err != nil {
		profile.TotalSec = time.Since(started).Seconds()
		return parseResult{Task: task, Entries: nil, Profile: profile}
	}

	lines := splitLines(data)
	profile.Lines = len(lines)

	parseStarted := time.Now()
	decls := gatherDecls(lines, task.Lang, cfg)
	commentDur := time.Duration(0)
	buildDur := time.Duration(0)
	entries := make([]Entry, 0, len(decls))
	for _, d := range decls {
		comment := ""
		if !cfg.DisableComments {
			tc := time.Now()
			comment = normalizeComment(extractComment(lines, d.Idx, task.Lang), task.Lang)
			commentDur += time.Since(tc)
		}
		tb := time.Now()
		entries = append(entries, Entry{
			Path:      fmt.Sprintf("%s::%s", task.RelPath, d.Name),
			Signature: normalizeSignature(d.Sig),
			Comment:   comment,
			Line:      d.Idx + 1,
			Kind:      d.Kind,
		})
		buildDur += time.Since(tb)
	}
	profile.ParseSec = time.Since(parseStarted).Seconds()
	profile.CommentSec = commentDur.Seconds()
	profile.BuildSec = buildDur.Seconds()
	profile.Entries = len(entries)
	profile.TotalSec = time.Since(started).Seconds()
	return parseResult{Task: task, Entries: entries, Profile: profile}
}

func gatherDecls(lines []string, lang string, cfg Config) []Decl {
	decls := make([]Decl, 0, 64)
	for i := 0; i < len(lines); {
		line := strings.TrimRight(lines[i], "\r")
		if len(line) > cfg.MaxParseLineLen {
			i++
			continue
		}
		trimmed := strings.TrimSpace(line)
		if trimmed == "" || isLineComment(line, lang) {
			i++
			continue
		}

		switch lang {
		case "swift":
			if m := swiftTypeRe.FindStringSubmatch(line); len(m) > 2 {
				decls = append(decls, Decl{Idx: i, Name: m[2], Sig: line, Kind: "type"})
				i++
				continue
			}
			if m := swiftCallableRe.FindStringSubmatch(line); len(m) > 1 {
				tok := m[1]
				name := ""
				switch {
				case strings.HasPrefix(tok, "func"):
					if n := swiftFuncNameRe.FindStringSubmatch(line); len(n) > 1 {
						name = n[1]
					}
				case strings.HasPrefix(tok, "init"):
					name = tok
				case tok == "deinit":
					name = "deinit"
				default:
					name = "subscript"
				}
				if name != "" {
					sig, end := collectSignature(lines, i, true, true, true, cfg.MaxSignatureLines)
					decls = append(decls, Decl{Idx: i, Name: name, Sig: sig, Kind: "callable"})
					i = end + 1
					continue
				}
			}
		case "objc":
			if m := objcTypeRe.FindStringSubmatch(line); len(m) > 1 {
				decls = append(decls, Decl{Idx: i, Name: m[1], Sig: line, Kind: "type"})
				i++
				continue
			}
			if objcMethodStartRe.MatchString(line) {
				sig, end := collectSignature(lines, i, true, true, false, cfg.MaxSignatureLines)
				decls = append(decls, Decl{Idx: i, Name: extractObjcName(sig), Sig: sig, Kind: "callable"})
				i = end + 1
				continue
			}
			if m := cFuncRe.FindStringSubmatch(line); len(m) > 2 && !isDisallowedCFunc(trimmed) {
				sig, end := collectSignature(lines, i, true, true, false, cfg.MaxSignatureLines)
				decls = append(decls, Decl{Idx: i, Name: m[2], Sig: sig, Kind: "callable"})
				i = end + 1
				continue
			}
		case "c", "cpp":
			if m := cTypeRe.FindStringSubmatch(line); len(m) > 2 {
				decls = append(decls, Decl{Idx: i, Name: m[2], Sig: line, Kind: "type"})
				i++
				continue
			}
			if strings.HasPrefix(trimmed, "typedef") {
				if m := cTypedefRe.FindStringSubmatch(line); len(m) > 1 {
					decls = append(decls, Decl{Idx: i, Name: m[1], Sig: line, Kind: "type"})
					i++
					continue
				}
			}
			if m := cFuncRe.FindStringSubmatch(line); len(m) > 2 && !isDisallowedCFunc(trimmed) {
				sig, end := collectSignature(lines, i, true, true, false, cfg.MaxSignatureLines)
				decls = append(decls, Decl{Idx: i, Name: m[2], Sig: sig, Kind: "callable"})
				i = end + 1
				continue
			}
		case "js", "ts":
			if m := jsTypeRe.FindStringSubmatch(line); len(m) > 2 {
				decls = append(decls, Decl{Idx: i, Name: m[2], Sig: line, Kind: "type"})
				i++
				continue
			}
			if m := firstSubmatch(line, jsFuncDeclRe, jsFuncExprRe, jsArrowRe); len(m) > 1 {
				sig, end := collectSignature(lines, i, true, true, false, cfg.MaxSignatureLines)
				decls = append(decls, Decl{Idx: i, Name: m[1], Sig: sig, Kind: "callable"})
				i = end + 1
				continue
			}
			if m := jsClassMethodInlineRe.FindStringSubmatch(line); len(m) > 1 {
				sig, end := collectSignature(lines, i, true, true, false, cfg.MaxSignatureLines)
				decls = append(decls, Decl{Idx: i, Name: m[1], Sig: sig, Kind: "callable"})
				i = end + 1
				continue
			}
		case "py":
			if m := pyClassRe.FindStringSubmatch(line); len(m) > 1 {
				decls = append(decls, Decl{Idx: i, Name: m[1], Sig: line, Kind: "type"})
				i++
				continue
			}
			if m := pyDefRe.FindStringSubmatch(line); len(m) > 1 {
				sig, end := collectSignature(lines, i, false, false, false, cfg.MaxSignatureLines)
				decls = append(decls, Decl{Idx: i, Name: m[1], Sig: sig, Kind: "callable"})
				i = end + 1
				continue
			}
		case "rb":
			if m := rbDefRe.FindStringSubmatch(line); len(m) > 1 {
				sig, end := collectSignature(lines, i, false, false, false, cfg.MaxSignatureLines)
				decls = append(decls, Decl{Idx: i, Name: m[1], Sig: sig, Kind: "callable"})
				i = end + 1
				continue
			}
		case "sh":
			if m := shFuncRe.FindStringSubmatch(line); len(m) > 1 {
				decls = append(decls, Decl{Idx: i, Name: m[1], Sig: line, Kind: "callable"})
				i++
				continue
			}
		case "kt":
			if m := ktTypeRe.FindStringSubmatch(line); len(m) > 2 {
				decls = append(decls, Decl{Idx: i, Name: m[2], Sig: line, Kind: "type"})
				i++
				continue
			}
			if m := ktFunRe.FindStringSubmatch(line); len(m) > 1 {
				sig, end := collectSignature(lines, i, true, true, false, cfg.MaxSignatureLines)
				decls = append(decls, Decl{Idx: i, Name: m[1], Sig: sig, Kind: "callable"})
				i = end + 1
				continue
			}
		case "java":
			if m := javaTypeRe.FindStringSubmatch(line); len(m) > 2 {
				decls = append(decls, Decl{Idx: i, Name: m[2], Sig: line, Kind: "type"})
				i++
				continue
			}
			if m := javaMethodRe.FindStringSubmatch(line); len(m) > 1 {
				sig, end := collectSignature(lines, i, true, true, false, cfg.MaxSignatureLines)
				decls = append(decls, Decl{Idx: i, Name: m[1], Sig: sig, Kind: "callable"})
				i = end + 1
				continue
			}
		}

		i++
	}
	return decls
}

func collectSignature(lines []string, start int, stopOnBrace, stopOnSemicolon, allowContinuation bool, maxLines int) (string, int) {
	sigLines := make([]string, 0, 4)
	paren := 0
	foundParen := false
	j := start
	for ; j < len(lines); j++ {
		if j-start+1 > maxLines {
			break
		}
		line := strings.TrimRight(lines[j], "\r")
		sigLines = append(sigLines, line)
		paren += parenDelta(line)
		if strings.Contains(line, "(") {
			foundParen = true
		}
		lineHasBrace := stopOnBrace && strings.Contains(line, "{")
		lineHasSemicolon := stopOnSemicolon && strings.Contains(line, ";")
		end := false
		if lineHasBrace || lineHasSemicolon {
			end = true
		} else if foundParen && paren == 0 {
			if allowContinuation && j+1 < len(lines) {
				nxt := strings.TrimSpace(lines[j+1])
				if strings.HasPrefix(nxt, "where") || strings.HasPrefix(nxt, "throws") || strings.HasPrefix(nxt, "rethrows") || strings.HasPrefix(nxt, "async") || strings.HasPrefix(nxt, "->") {
					continue
				}
			}
			end = true
		}
		if end {
			break
		}
	}
	if len(sigLines) > 1 && strings.TrimSpace(sigLines[len(sigLines)-1]) == "{" {
		sigLines = sigLines[:len(sigLines)-1]
		j--
	}
	return strings.Join(sigLines, "\n"), j
}

func parenDelta(line string) int {
	delta := 0
	inSingle := false
	inDouble := false
	escaped := false
	for _, ch := range line {
		if escaped {
			escaped = false
			continue
		}
		if ch == '\\' {
			escaped = true
			continue
		}
		if inSingle {
			if ch == '\'' {
				inSingle = false
			}
			continue
		}
		if inDouble {
			if ch == '"' {
				inDouble = false
			}
			continue
		}
		if ch == '\'' {
			inSingle = true
			continue
		}
		if ch == '"' {
			inDouble = true
			continue
		}
		if ch == '(' {
			delta++
		} else if ch == ')' {
			delta--
		}
	}
	return delta
}

func extractObjcName(signature string) string {
	s := strings.Join(strings.Fields(signature), " ")
	parts := regexp.MustCompile(`([A-Za-z_][A-Za-z0-9_]*)\s*:`).FindAllStringSubmatch(s, -1)
	if len(parts) > 0 {
		names := make([]string, 0, len(parts))
		for _, p := range parts {
			names = append(names, p[1])
		}
		return strings.Join(names, ":") + ":"
	}
	if m := regexp.MustCompile(`\)\s*([A-Za-z_][A-Za-z0-9_]*)`).FindStringSubmatch(s); len(m) > 1 {
		return m[1]
	}
	return "unknown"
}

func normalizeSignature(signature string) string {
	if signature == "" {
		return ""
	}
	lines := strings.Split(signature, "\n")
	for len(lines) > 0 && strings.TrimSpace(lines[0]) == "" {
		lines = lines[1:]
	}
	for len(lines) > 0 && strings.TrimSpace(lines[len(lines)-1]) == "" {
		lines = lines[:len(lines)-1]
	}
	if len(lines) == 0 {
		return ""
	}
	minIndent := -1
	for _, ln := range lines {
		if strings.TrimSpace(ln) == "" {
			continue
		}
		ind := leadingIndent(ln)
		if minIndent < 0 || ind < minIndent {
			minIndent = ind
		}
	}
	if minIndent > 0 {
		for i, ln := range lines {
			if len(ln) >= minIndent {
				lines[i] = ln[minIndent:]
			}
		}
	}
	collapsed := make([]string, 0, len(lines))
	lastBlank := false
	for _, ln := range lines {
		blank := strings.TrimSpace(ln) == ""
		if blank {
			if !lastBlank {
				collapsed = append(collapsed, "")
			}
			lastBlank = true
		} else {
			collapsed = append(collapsed, strings.TrimRight(ln, " \t"))
			lastBlank = false
		}
	}
	return strings.Join(collapsed, "\n")
}

func leadingIndent(s string) int {
	count := 0
	for _, r := range s {
		if r == ' ' || r == '\t' {
			count++
		} else {
			break
		}
	}
	return count
}

func extractComment(lines []string, idx int, lang string) string {
	j := idx - 1
	for j >= 0 && (decoratorRe.MatchString(lines[j]) || (cLikeLang[lang] && preprocessorRe.MatchString(lines[j]))) {
		j--
	}
	if j < 0 {
		return ""
	}
	if strings.TrimSpace(lines[j]) == "" {
		return ""
	}

	line := lines[j]
	if isLineComment(line, lang) {
		block := []string{strings.TrimRight(line, "\r")}
		j--
		for j >= 0 && isLineComment(lines[j], lang) {
			block = append(block, strings.TrimRight(lines[j], "\r"))
			j--
		}
		reverseStrings(block)
		return strings.Join(block, "\n")
	}

	if isBlockCommentBoundary(line, lang) {
		block := []string{strings.TrimRight(line, "\r")}
		j--
		for j >= 0 {
			cur := strings.TrimRight(lines[j], "\r")
			block = append(block, cur)
			if isBlockCommentStart(cur, lang) {
				break
			}
			j--
		}
		reverseStrings(block)
		return strings.Join(block, "\n")
	}

	return ""
}

func isLineComment(line, lang string) bool {
	s := strings.TrimLeftFunc(line, unicode.IsSpace)
	if hashCommentLang[lang] {
		return strings.HasPrefix(s, "#")
	}
	if cLikeLang[lang] {
		return strings.HasPrefix(s, "//")
	}
	return false
}

func isBlockCommentBoundary(line, lang string) bool {
	s := strings.TrimLeftFunc(line, unicode.IsSpace)
	if cLikeLang[lang] {
		return strings.Contains(s, "/*") || strings.Contains(s, "*/")
	}
	if lang == "rb" {
		t := strings.TrimSpace(s)
		return t == "=begin" || t == "=end"
	}
	if lang == "py" {
		t := strings.TrimSpace(s)
		return strings.HasPrefix(t, `"""`) || strings.HasPrefix(t, `'''`)
	}
	return false
}

func isBlockCommentStart(line, lang string) bool {
	s := strings.TrimLeftFunc(line, unicode.IsSpace)
	if cLikeLang[lang] {
		return strings.Contains(s, "/*")
	}
	if lang == "rb" {
		return strings.TrimSpace(s) == "=begin"
	}
	if lang == "py" {
		t := strings.TrimSpace(s)
		return strings.HasPrefix(t, `"""`) || strings.HasPrefix(t, `'''`)
	}
	return false
}

func normalizeComment(comment, lang string) string {
	if comment == "" {
		return ""
	}
	lines := strings.Split(comment, "\n")
	cleaned := make([]string, 0, len(lines))
	for _, ln := range lines {
		s := strings.TrimLeftFunc(ln, unicode.IsSpace)
		if cLikeLang[lang] {
			if strings.HasPrefix(s, "//") {
				s = strings.TrimPrefix(s, "//")
				s = strings.TrimPrefix(s, " ")
			}
			if strings.HasPrefix(s, "/*") {
				s = strings.TrimPrefix(s, "/*")
				s = strings.TrimPrefix(s, " ")
			}
			if strings.HasSuffix(s, "*/") {
				s = strings.TrimSpace(strings.TrimSuffix(s, "*/"))
			}
			if strings.HasPrefix(s, "*") {
				s = strings.TrimPrefix(s, "*")
				s = strings.TrimPrefix(s, " ")
			}
		}
		if hashCommentLang[lang] {
			if strings.HasPrefix(s, "#") {
				s = strings.TrimPrefix(s, "#")
				s = strings.TrimPrefix(s, " ")
			}
		}
		cleaned = append(cleaned, strings.TrimRight(s, " \t"))
	}

	collapsed := make([]string, 0, len(cleaned))
	lastBlank := false
	for _, ln := range cleaned {
		blank := strings.TrimSpace(ln) == ""
		if blank {
			if !lastBlank {
				collapsed = append(collapsed, "")
			}
			lastBlank = true
		} else {
			collapsed = append(collapsed, ln)
			lastBlank = false
		}
	}
	for len(collapsed) > 0 && collapsed[0] == "" {
		collapsed = collapsed[1:]
	}
	for len(collapsed) > 0 && collapsed[len(collapsed)-1] == "" {
		collapsed = collapsed[:len(collapsed)-1]
	}
	return strings.Join(collapsed, "\n")
}

func reverseStrings(xs []string) {
	for i, j := 0, len(xs)-1; i < j; i, j = i+1, j-1 {
		xs[i], xs[j] = xs[j], xs[i]
	}
}

func firstSubmatch(line string, res ...*regexp.Regexp) []string {
	for _, re := range res {
		if m := re.FindStringSubmatch(line); len(m) > 0 {
			return m
		}
	}
	return nil
}

func isDisallowedCFunc(trimmed string) bool {
	lower := strings.ToLower(strings.TrimSpace(trimmed))
	for _, p := range []string{"if", "for", "while", "switch", "catch", "return", "typedef", "struct", "class", "enum", "#", "using", "namespace", "template", "static_assert"} {
		if strings.HasPrefix(lower, p) {
			if len(lower) == len(p) {
				return true
			}
			next := lower[len(p)]
			if !((next >= 'a' && next <= 'z') || (next >= '0' && next <= '9') || next == '_') {
				return true
			}
		}
	}
	return false
}

func splitLines(data []byte) []string {
	if len(data) == 0 {
		return []string{}
	}
	s := string(data)
	return strings.Split(s, "\n")
}

func collectCandidates(root string, cfg Config) ([]Candidate, string, error) {
	if cands, err := collectCandidatesGit(root, cfg); err == nil {
		return cands, "git", nil
	}
	cands, err := collectCandidatesWalk(root, cfg)
	if err != nil {
		return nil, "", err
	}
	return cands, "walk", nil
}

func collectCandidatesGit(root string, cfg Config) ([]Candidate, error) {
	cmd := exec.Command("git", "-C", root, "ls-files", "-co", "--exclude-standard")
	out, err := cmd.Output()
	if err != nil {
		return nil, err
	}
	seen := make(map[string]bool)
	cands := make([]Candidate, 0, 4096)
	for _, raw := range strings.Split(string(out), "\n") {
		rel := filepath.ToSlash(strings.TrimSpace(raw))
		if rel == "" || seen[rel] {
			continue
		}
		seen[rel] = true
		cand, ok := makeCandidate(root, rel, cfg)
		if ok {
			cands = append(cands, cand)
		}
	}
	sort.Slice(cands, func(i, j int) bool { return cands[i].RelPath < cands[j].RelPath })
	return cands, nil
}

func collectCandidatesWalk(root string, cfg Config) ([]Candidate, error) {
	cands := make([]Candidate, 0, 4096)
	err := filepath.WalkDir(root, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return nil
		}
		rel, err := filepath.Rel(root, path)
		if err != nil {
			return nil
		}
		rel = filepath.ToSlash(rel)
		if rel == "." {
			return nil
		}
		if d.IsDir() {
			if shouldSkipDir(rel) {
				return filepath.SkipDir
			}
			return nil
		}
		cand, ok := makeCandidate(root, rel, cfg)
		if ok {
			cands = append(cands, cand)
		}
		return nil
	})
	if err != nil {
		return nil, err
	}
	sort.Slice(cands, func(i, j int) bool { return cands[i].RelPath < cands[j].RelPath })
	return cands, nil
}

func makeCandidate(root, rel string, cfg Config) (Candidate, bool) {
	if pathHasExcludedDir(rel) {
		return Candidate{}, false
	}
	if shouldSkipGeneratedAsset(rel, cfg) {
		return Candidate{}, false
	}
	abs := filepath.Join(root, filepath.FromSlash(rel))
	st, err := os.Stat(abs)
	if err != nil || st.IsDir() {
		return Candidate{}, false
	}
	lang, ok := detectLang(abs, filepath.Base(rel))
	if !ok {
		return Candidate{}, false
	}
	return Candidate{
		RelPath: rel,
		AbsPath: abs,
		Lang:    lang,
		Size:    st.Size(),
		MtimeNs: mtimeNs(st),
	}, true
}

func isExcludedDirName(lowerName string) bool {
	if excludeDirLower[lowerName] {
		return true
	}
	for _, suffix := range excludeDirSuffixes {
		if strings.HasSuffix(lowerName, suffix) {
			return true
		}
	}
	return false
}

func pathHasExcludedDir(rel string) bool {
	lower := strings.ToLower(filepath.ToSlash(rel))
	if strings.HasPrefix(lower, "tuist/dependencies/") {
		return true
	}
	parts := strings.Split(lower, "/")
	for i := 0; i < len(parts)-1; i++ {
		if isExcludedDirName(parts[i]) {
			return true
		}
	}
	return false
}

func shouldSkipDir(rel string) bool {
	lower := strings.ToLower(filepath.ToSlash(rel))
	if strings.HasPrefix(lower, "tuist/dependencies") {
		return true
	}
	parts := strings.Split(lower, "/")
	for _, p := range parts {
		if isExcludedDirName(p) {
			return true
		}
	}
	return false
}

func shouldSkipGeneratedAsset(rel string, cfg Config) bool {
	if cfg.IndexHashedBundles {
		return false
	}
	base := strings.ToLower(filepath.Base(rel))
	if strings.HasSuffix(base, ".js") && hashedAssetRe.MatchString(base) {
		return true
	}
	return false
}

func detectLang(absPath, filename string) (string, bool) {
	ext := strings.ToLower(filepath.Ext(filename))
	if lang, ok := langByExt[ext]; ok {
		return lang, true
	}
	if ext != "" {
		return "", false
	}
	f, err := os.Open(absPath)
	if err != nil {
		return "", false
	}
	defer f.Close()
	r := bufio.NewReader(f)
	line, err := r.ReadString('\n')
	if err != nil && !errors.Is(err, io.EOF) {
		return "", false
	}
	line = strings.TrimSpace(line)
	if strings.HasPrefix(line, "#!") {
		l := strings.ToLower(line)
		switch {
		case strings.Contains(l, "python"):
			return "py", true
		case strings.Contains(l, "ruby"):
			return "rb", true
		case strings.Contains(l, "bash"), strings.Contains(l, "sh"), strings.Contains(l, "zsh"):
			return "sh", true
		}
	}
	return "", false
}

func loadEntries(path string) ([]Entry, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	var entries []Entry
	dec := json.NewDecoder(f)
	if err := dec.Decode(&entries); err != nil {
		return nil, err
	}
	return entries, nil
}

func writeEntries(path string, entries []Entry) error {
	f, err := os.Create(path)
	if err != nil {
		return err
	}
	defer f.Close()
	enc := json.NewEncoder(f)
	enc.SetEscapeHTML(false)
	return enc.Encode(entries)
}

func loadMeta(path string) (*Meta, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	var meta Meta
	if err := json.NewDecoder(f).Decode(&meta); err != nil {
		return nil, err
	}
	if meta.Files == nil {
		meta.Files = map[string]FileMeta{}
	}
	return &meta, nil
}

func writeMeta(path string, meta *Meta) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	f, err := os.Create(path)
	if err != nil {
		return err
	}
	defer f.Close()
	enc := json.NewEncoder(f)
	enc.SetEscapeHTML(false)
	enc.SetIndent("", "  ")
	return enc.Encode(meta)
}

func metaPathForRoot(root, cacheDir string) string {
	sum := sha1.Sum([]byte(root))
	return filepath.Join(cacheDir, fmt.Sprintf("%x.meta.json", sum))
}

func gitState(root, outPath string) *GitState {
	headCmd := exec.Command("git", "-C", root, "rev-parse", "HEAD")
	headOut, err := headCmd.Output()
	if err != nil {
		return nil
	}
	head := strings.TrimSpace(string(headOut))
	if head == "" {
		return nil
	}

	outRel := ""
	if rel, err := filepath.Rel(root, outPath); err == nil && !strings.HasPrefix(rel, "..") {
		outRel = filepath.ToSlash(rel)
	}

	statusCmd := exec.Command("git", "-C", root, "status", "--porcelain=v1", "--untracked-files=all")
	statusOut, err := statusCmd.Output()
	clean := true
	if err == nil {
		for _, raw := range strings.Split(string(statusOut), "\n") {
			line := strings.TrimSpace(raw)
			if line == "" {
				continue
			}
			pathPart := line
			if len(pathPart) >= 4 {
				pathPart = strings.TrimSpace(pathPart[3:])
			}
			if strings.Contains(pathPart, " -> ") {
				parts := strings.SplitN(pathPart, " -> ", 2)
				pathPart = parts[1]
			}
			pathPart = strings.Trim(pathPart, `"`)
			pathPart = filepath.ToSlash(pathPart)
			if outRel != "" && pathPart == outRel {
				continue
			}
			clean = false
			break
		}
	} else {
		clean = false
	}

	return &GitState{Head: head, Clean: clean}
}

func printTopProfiles(profiles []FileProfile, topN int) {
	if len(profiles) == 0 {
		return
	}
	sort.Slice(profiles, func(i, j int) bool {
		if profiles[i].TotalSec == profiles[j].TotalSec {
			return profiles[i].Path < profiles[j].Path
		}
		return profiles[i].TotalSec > profiles[j].TotalSec
	})
	if topN > len(profiles) {
		topN = len(profiles)
	}
	fmt.Fprintln(os.Stderr, "SIGMAP PROFILE top files:")
	for i := 0; i < topN; i++ {
		p := profiles[i]
		fmt.Fprintf(
			os.Stderr,
			"%2d) %s | lang=%s size=%d lines=%d entries=%d total=%.3fs read=%.3fs parse=%.3fs comment=%.3fs build=%.3fs\n",
			i+1, p.Path, p.Lang, p.SizeBytes, p.Lines, p.Entries, p.TotalSec, p.ReadSec, p.ParseSec, p.CommentSec, p.BuildSec,
		)
	}
}

func mtimeNs(st fs.FileInfo) int64 {
	return st.ModTime().UnixNano()
}

func detectRootFromCwd() (string, error) {
	cmd := exec.Command("git", "rev-parse", "--show-toplevel")
	out, err := cmd.Output()
	if err != nil {
		return "", err
	}
	root := strings.TrimSpace(string(out))
	if root == "" {
		return "", errors.New("empty git root")
	}
	return root, nil
}

func envBool(name string, def bool) bool {
	v := strings.TrimSpace(os.Getenv(name))
	if v == "" {
		return def
	}
	switch strings.ToLower(v) {
	case "1", "true", "yes", "on":
		return true
	case "0", "false", "no", "off":
		return false
	default:
		return def
	}
}

func envInt(name string, def int) int {
	v := strings.TrimSpace(os.Getenv(name))
	if v == "" {
		return def
	}
	n, err := strconv.Atoi(v)
	if err != nil {
		return def
	}
	return n
}

func envString(name, def string) string {
	v := strings.TrimSpace(os.Getenv(name))
	if v == "" {
		return def
	}
	return v
}

func minInt(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func maxInt(a, b int) int {
	if a > b {
		return a
	}
	return b
}
