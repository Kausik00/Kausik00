# Chapter 33: Kubernetes Services, Ingress, and Network Policies

*DevOps Handbook — Part VIII, Pages 631–655*

---

## 33.1 Kubernetes networking model

Every pod gets a cluster-routable **IP address**. Pods can talk to any other pod without NAT (CNI permitting). **Services** provide stable virtual IPs and DNS names in front of ephemeral pod IPs. **Ingress** (or Gateway API) routes HTTP/S from outside the cluster to Services.

```
Internet → Load Balancer → Ingress Controller → Service → Pod endpoints
```

---

## 33.2 Service types

```yaml
apiVersion: v1
kind: Service
metadata:
  name: api
spec:
  type: ClusterIP
  selector:
    app: api
  ports:
    - port: 80
      targetPort: 8080
      protocol: TCP
```

| Type | Reachability | Use case |
|------|--------------|----------|
| **ClusterIP** | Internal only | Default; microservice-to-microservice |
| **NodePort** | Host port 30000–32767 | Dev, legacy exposure |
| **LoadBalancer** | Cloud LB → Service | Public APIs on managed clouds |
| **ExternalName** | DNS CNAME | External SaaS alias |

DNS inside cluster: `api.default.svc.cluster.local` (short: `api` in same namespace).

```bash
kubectl get svc
kubectl get endpoints api
kubectl run -it --rm debug --image=busybox -- wget -qO- http://api
```

**Headless Service** (`clusterIP: None`) returns pod A records directly—used by StatefulSets.

---

## 33.3 Endpoints and EndpointSlices

The **Endpoints** (or **EndpointSlice**) controller populates backend pod IPs for Services matching `selector`. Readiness probe failure removes a pod from endpoints—traffic stops without deleting the pod.

```bash
kubectl get endpointslices -l kubernetes.io/service-name=api
```

Services without selectors can manually point to external IPs:

```yaml
spec:
  ports:
    - port: 443
  type: ClusterIP
---
apiVersion: v1
kind: Endpoints
metadata:
  name: external-db
subsets:
  - addresses:
      - ip: 10.0.50.10
    ports:
      - port: 5432
```

---

## 33.4 Ingress — HTTP routing

**Ingress** requires an **Ingress Controller** (nginx, traefik, AWS ALB, etc.).

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: web-ingress
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - app.example.com
      secretName: app-tls
  rules:
    - host: app.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: frontend
                port:
                  number: 80
    - host: api.example.com
      http:
        paths:
          - path: /v1
            pathType: Prefix
            backend:
              service:
                name: api
                port:
                  number: 80
```

| `pathType` | Match |
|------------|-------|
| `Prefix` | `/api` matches `/api/users` |
| `Exact` | Exact path only |
| `ImplementationSpecific` | Controller-defined |

Annotations configure TLS, redirects, rate limits, body size—varies by controller.

---

## 33.5 LoadBalancer and NodePort in cloud

EKS example — Service type LoadBalancer provisions an ELB:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: api-public
  annotations:
    service.beta.kubernetes.io/aws-load-balancer-type: "nlb"
    service.beta.kubernetes.io/aws-load-balancer-scheme: "internet-facing"
spec:
  type: LoadBalancer
  selector:
    app: api
  ports:
    - port: 443
      targetPort: 8080
```

Prefer **Ingress** or **Gateway API** over many LoadBalancers—cost and IP management.

---

## 33.6 Gateway API (modern alternative)

Gateway API separates **Gateway** (infrastructure) from **HTTPRoute** (application routing):

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: api-route
spec:
  parentRefs:
    - name: public-gateway
  hostnames:
    - api.example.com
  rules:
    - matches:
        - path:
            type: PathPrefix
            value: /v1
      backendRefs:
        - name: api
          port: 80
```

More expressive than Ingress; adoption growing on cloud providers.

---

## 33.7 Network Policies — zero trust inside the cluster

By default, all pods can reach all pods (**allow-all**). **NetworkPolicy** restricts traffic at L3/L4.

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: api-allow
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: api
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: frontend
        - namespaceSelector:
            matchLabels:
              name: ingress-nginx
      ports:
        - protocol: TCP
          port: 8080
  egress:
    - to:
        - podSelector:
            matchLabels:
              app: postgres
      ports:
        - protocol: TCP
          port: 5432
    - to:                          # DNS
        - namespaceSelector: {}
          podSelector:
            matchLabels:
              k8s-app: kube-dns
      ports:
        - protocol: UDP
          port: 53
```

Requires a CNI that enforces NetworkPolicy (**Calico**, **Cilium**, **Weave**). AWS VPC CNI needs policy enforcement addon.

**Default deny** pattern:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
spec:
  podSelector: {}
  policyTypes: [Ingress, Egress]
```

Then add explicit allow policies per app.

---

## 33.8 Debugging connectivity

```bash
kubectl run netshoot --rm -it --image=nicolaka/netshoot -- bash
curl -v http://api.production.svc.cluster.local
nslookup api.production.svc.cluster.local
kubectl describe networkpolicy -n production
kubectl get ingress
kubectl logs -n ingress-nginx deploy/ingress-nginx-controller
```

| Symptom | Check |
|---------|-------|
| 503 from Ingress | Endpoints empty? Readiness failing? |
| Timeout pod-to-pod | NetworkPolicy deny? Wrong namespace DNS? |
| Works by IP not name | CoreDNS issue |
| External no route | LB security groups, Ingress class |

---

## 33.9 Chapter summary

- **Services** abstract pod IPs with ClusterIP, NodePort, and LoadBalancer types.
- **Ingress** (or **Gateway API**) routes HTTP host/path to Services; requires a controller.
- **NetworkPolicies** implement least-privilege pod communication—start with default deny in production namespaces.
- Always verify **endpoints** and **readiness** when traffic fails mysteriously.

---

## 🧪 Lab 33.1

1. Expose a Deployment with ClusterIP; reach it from a debug pod via DNS.
2. Install nginx Ingress Controller; route two hostnames to two Services.
3. Add TLS with cert-manager (or self-signed for lab).

---

## 🧪 Lab 33.2

1. Apply default-deny NetworkPolicy in a namespace.
2. Add allow rules so frontend → api → postgres works; verify blocked paths fail.
3. Document required egress to kube-dns for DNS resolution.

---

## Review questions

1. How does a Service know which pods to send traffic to?
2. What is the difference between ClusterIP and Headless Services?
3. Why does Ingress require a separate controller?
4. What happens to Service traffic when all pods fail readiness?
5. Which CNIs enforce NetworkPolicy, and what breaks if yours does not?

---

*Next: [Chapter 34 — K8s Config and Storage](./chapter-34-k8s-config-storage.md)*
