package httpservice

import (
	myconfig "OpenInfoServices/config"
	"bytes"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
)

type KeycloakTokenResponse struct {
	AccessToken string `json:"access_token"`
}

func getBearerToken() (string, error) {
	keycloakurl, keycloakrealm, keycloakclientid, keycloakclientsecret, keycloakuser, keycloakpassword := myconfig.GetKeycloak()

	url := keycloakurl + "/auth/realms/" + keycloakrealm + "/protocol/openid-connect/token"
	// data := "client_id=" + keycloakclientid + "&client_secret=" + keycloakclientsecret + "&grant_type=client_credentials"
	data := fmt.Sprintf("client_id=%s&client_secret=%s&grant_type=password&username=%s&password=%s", keycloakclientid, keycloakclientsecret, keycloakuser, keycloakpassword)

	req, err := http.NewRequest("POST", url, bytes.NewBufferString(data))
	if err != nil {
		return "", err
	}
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")

	// Create a custom transport with TLS verification disabled
	tr := &http.Transport{
		TLSClientConfig: &tls.Config{InsecureSkipVerify: true},
	}
	client := &http.Client{Transport: tr}

	resp, err := client.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", err
	}

	var tokenResponse KeycloakTokenResponse
	err = json.Unmarshal(body, &tokenResponse)
	if err != nil {
		return "", err
	}

	return tokenResponse.AccessToken, nil
}

func HttpPost(endpoint string, payload map[string]int) ([]byte, error) {
	bearerToken, err0 := getBearerToken()
	if err0 != nil {
		log.Fatalf("Failed to get Bearer token: %v", err0)
	}

	jsonPayload, err1 := json.Marshal(payload)
	if err1 != nil {
		return nil, err1
	}

	req, err2 := http.NewRequest("POST", endpoint, bytes.NewBuffer(jsonPayload))
	if err2 != nil {
		return nil, err2
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", bearerToken))

	client := &http.Client{}
	resp, err3 := client.Do(req)
	if err3 != nil {
		return nil, err3
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	if resp.StatusCode != http.StatusOK {
		return body, fmt.Errorf("received non-200 response code: %d", resp.StatusCode)
	}

	return body, nil
}

func HttpGet(endpoint string) ([]byte, error) {
	bearerToken, err0 := getBearerToken()
	if err0 != nil {
		log.Fatalf("Failed to get Bearer token: %v", err0)
	}
	fmt.Printf("token: %s", bearerToken)

	req, err1 := http.NewRequest("GET", endpoint, nil)
	if err1 != nil {
		return nil, err1
	}
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", bearerToken))

	client := &http.Client{}
	resp, err2 := client.Do(req)
	if err2 != nil {
		return nil, err2
	}
	defer resp.Body.Close()

	body, err3 := io.ReadAll(resp.Body)
	if err3 != nil {
		return nil, err3
	}

	if resp.StatusCode != http.StatusOK {
		return body, fmt.Errorf("received non-200 response code: %d", resp.StatusCode)
	}

	return body, nil
}
