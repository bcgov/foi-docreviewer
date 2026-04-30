package sitemapping

import (
	"context"
	"errors"
	"fmt"
	"path"
	"strings"
	"time"

	pub "publication-service/internal/publish"
)

type ResultStore interface {
	FindCompleted(ctx context.Context, kind pub.Kind, publicationID string) (Result, bool, error)
	MarkSucceeded(ctx context.Context, eventID string, result Result) error
}

type Writer struct {
	store   ObjectStore
	repo    ResultStore
	targets map[pub.Kind]Target
	now     func() time.Time
}

func NewWriter(store ObjectStore, repo ResultStore, targets map[pub.Kind]Target) *Writer {
	return &Writer{
		store:   store,
		repo:    repo,
		targets: targets,
		now:     func() time.Time { return time.Now().UTC() },
	}
}

func (w *Writer) Handle(ctx context.Context, req Request) (Result, error) {
	if existing, ok, err := w.repo.FindCompleted(ctx, req.Kind, req.PublicationID); err != nil || ok {
		return existing, err
	}
	target, ok := w.targets[req.Kind]
	if !ok {
		return Result{}, pub.NewPermanent("sitemapping: no target configured for kind " + string(req.Kind))
	}
	if target.PageLimit <= 0 {
		return Result{}, pub.NewPermanent("sitemapping: page limit must be positive")
	}
	if target.IndexFileName == "" {
		return Result{}, pub.NewPermanent("sitemapping: index file name is required")
	}
	if target.PageFilePattern == "" {
		return Result{}, pub.NewPermanent("sitemapping: page file pattern is required")
	}

	selection, err := w.selectPage(ctx, target, req)
	if err != nil {
		return Result{}, err
	}
	if !selection.Page.Contains(req.PublicURL) {
		selection.Page.Append(URLEntry{Loc: req.PublicURL, LastMod: req.LastModified.Format("2006-01-02")})
	}
	pageXML, err := selection.Page.Render()
	if err != nil {
		return Result{}, err
	}
	if err := w.store.Upload(ctx, target.Bucket, selection.PageKey, pageXML, "application/xml"); err != nil {
		return Result{}, err
	}
	if selection.IndexUpdated {
		indexXML, err := selection.Index.Render()
		if err != nil {
			return Result{}, err
		}
		if err := w.store.Upload(ctx, target.Bucket, selection.IndexKey, indexXML, "application/xml"); err != nil {
			return Result{}, err
		}
	}
	result := Result{
		Kind:                 req.Kind,
		TenantID:             req.TenantID,
		PublicationID:        req.PublicationID,
		PublicURL:            req.PublicURL,
		LastModified:         req.LastModified,
		SitemapIndexKey:      selection.IndexKey,
		SitemapPageKey:       selection.PageKey,
		SitemapPageURL:       selection.PageURL,
		Status:               selection.Status,
		IndexUpdated:         selection.IndexUpdated,
		PublicationResultRef: req.PublicationResultRef,
		CompletedAt:          w.now(),
	}
	if err := w.repo.MarkSucceeded(ctx, req.SourceEventID, result); err != nil {
		return Result{}, err
	}
	return result, nil
}

func (w *Writer) Remove(ctx context.Context, req RemovalRequest) (RemovalResult, error) {
	target, ok := w.targets[req.Kind]
	if !ok {
		return RemovalResult{}, pub.NewPermanent("sitemapping: no target configured for kind " + string(req.Kind))
	}
	if target.IndexFileName == "" {
		return RemovalResult{}, pub.NewPermanent("sitemapping: index file name is required")
	}

	indexKey := objectKey(target.Prefix, target.IndexFileName)
	rawIndex, err := w.store.Get(ctx, target.Bucket, indexKey)
	if errors.Is(err, ErrObjectNotFound) {
		return w.removalResult(req, indexKey, "", "", RemovalStatusAlreadyAbsent, false), nil
	}
	if err != nil {
		return RemovalResult{}, err
	}
	index, err := ParseSitemapIndex(rawIndex)
	if err != nil {
		return RemovalResult{}, err
	}

	for _, entry := range append([]SitemapEntry(nil), index.Sitemaps...) {
		pageKey, err := sitemapLocKey(target, entry.Loc)
		if err != nil {
			return RemovalResult{}, err
		}
		rawPage, err := w.store.Get(ctx, target.Bucket, pageKey)
		if errors.Is(err, ErrObjectNotFound) {
			continue
		}
		if err != nil {
			return RemovalResult{}, err
		}
		pageSet, err := ParseURLSet(rawPage)
		if err != nil {
			return RemovalResult{}, err
		}
		if !pageSet.Remove(req.PublicURL) {
			continue
		}
		if !pageSet.Empty() {
			pageXML, err := pageSet.Render()
			if err != nil {
				return RemovalResult{}, err
			}
			if err := w.store.Upload(ctx, target.Bucket, pageKey, pageXML, "application/xml"); err != nil {
				return RemovalResult{}, err
			}
			return w.removalResult(req, indexKey, pageKey, entry.Loc, RemovalStatusRemoved, false), nil
		}
		if err := w.store.Delete(ctx, target.Bucket, pageKey); err != nil {
			return RemovalResult{}, err
		}
		index.Remove(entry.Loc)
		indexXML, err := index.Render()
		if err != nil {
			return RemovalResult{}, err
		}
		if err := w.store.Upload(ctx, target.Bucket, indexKey, indexXML, "application/xml"); err != nil {
			return RemovalResult{}, err
		}
		return w.removalResult(req, indexKey, pageKey, entry.Loc, RemovalStatusPageDeleted, true), nil
	}

	return w.removalResult(req, indexKey, "", "", RemovalStatusAlreadyAbsent, false), nil
}

func (w *Writer) removalResult(req RemovalRequest, indexKey, pageKey, pageURL string, status RemovalStatus, indexUpdated bool) RemovalResult {
	return RemovalResult{
		Kind:            req.Kind,
		TenantID:        req.TenantID,
		PublicationID:   req.PublicationID,
		PublicURL:       req.PublicURL,
		LastModified:    req.LastModified,
		SitemapIndexKey: indexKey,
		SitemapPageKey:  pageKey,
		SitemapPageURL:  pageURL,
		Status:          status,
		IndexUpdated:    indexUpdated,
		CompletedAt:     w.now(),
	}
}

type pageSelection struct {
	Index        SitemapIndex
	Page         URLSet
	IndexKey     string
	PageKey      string
	PageURL      string
	Status       Status
	IndexUpdated bool
}

func (w *Writer) selectPage(ctx context.Context, target Target, req Request) (pageSelection, error) {
	indexKey := objectKey(target.Prefix, target.IndexFileName)
	rawIndex, err := w.store.Get(ctx, target.Bucket, indexKey)
	if errors.Is(err, ErrObjectNotFound) {
		index := NewSitemapIndex()
		return w.newPageSelection(index, target, req, indexKey, 1)
	}
	if err != nil {
		return pageSelection{}, err
	}
	index, err := ParseSitemapIndex(rawIndex)
	if err != nil {
		return pageSelection{}, err
	}
	if len(index.Sitemaps) == 0 {
		return w.newPageSelection(index, target, req, indexKey, 1)
	}

	last := index.Sitemaps[len(index.Sitemaps)-1]
	pageKey, err := sitemapLocKey(target, last.Loc)
	if err != nil {
		return pageSelection{}, err
	}
	rawPage, err := w.store.Get(ctx, target.Bucket, pageKey)
	if errors.Is(err, ErrObjectNotFound) {
		rawPage = nil
	} else if err != nil {
		return pageSelection{}, err
	}
	pageSet, err := ParseURLSet(rawPage)
	if err != nil {
		return pageSelection{}, err
	}
	if pageSet.Contains(req.PublicURL) {
		return pageSelection{
			Index:        index,
			Page:         pageSet,
			IndexKey:     indexKey,
			PageKey:      pageKey,
			PageURL:      last.Loc,
			Status:       StatusAlreadyPresent,
			IndexUpdated: false,
		}, nil
	}
	if len(pageSet.URLs) < target.PageLimit {
		return pageSelection{
			Index:        index,
			Page:         pageSet,
			IndexKey:     indexKey,
			PageKey:      pageKey,
			PageURL:      last.Loc,
			Status:       StatusWritten,
			IndexUpdated: false,
		}, nil
	}
	return w.newPageSelection(index, target, req, indexKey, len(index.Sitemaps)+1)
}

func (w *Writer) newPageSelection(index SitemapIndex, target Target, req Request, indexKey string, pageNumber int) (pageSelection, error) {
	pageName := fmt.Sprintf(target.PageFilePattern, pageNumber)
	pageKey := objectKey(target.Prefix, pageName)
	pageURL := joinURL(target.PublicBaseURL, pageName)
	index.Append(SitemapEntry{
		Loc:     pageURL,
		LastMod: req.LastModified.Format("2006-01-02"),
	})
	return pageSelection{
		Index:        index,
		Page:         NewURLSet(),
		IndexKey:     indexKey,
		PageKey:      pageKey,
		PageURL:      pageURL,
		Status:       StatusWritten,
		IndexUpdated: true,
	}, nil
}

func objectKey(prefix, name string) string {
	prefix = strings.Trim(prefix, "/")
	name = strings.TrimLeft(name, "/")
	if prefix == "" {
		return name
	}
	return prefix + "/" + name
}

func joinURL(base, key string) string {
	return strings.TrimRight(base, "/") + "/" + strings.TrimLeft(key, "/")
}

func sitemapLocKey(target Target, loc string) (string, error) {
	base := strings.TrimRight(target.PublicBaseURL, "/") + "/"
	if strings.HasPrefix(loc, base) {
		return objectKey(target.Prefix, strings.TrimPrefix(loc, base)), nil
	}
	if strings.Contains(loc, target.Prefix) {
		return objectKey(target.Prefix, path.Base(loc)), nil
	}
	return "", pub.NewPermanent("sitemapping: sitemap loc outside configured public base url")
}
