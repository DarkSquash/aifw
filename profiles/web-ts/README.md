# Web profile

An optional stack profile for React, JavaScript, TypeScript and other web systems. It adds boundaries, contract, design-system, security and observability expectations without dictating a specific framework, language variant, database, component library or hosting provider.

Activate it during initialization with `aifw init --web`. The internal id remains `web-ts` for compatibility with existing manifests.

Select it only after Project Intake or repository discovery supports that choice. Framework-wide rules stay in `policies/core.yaml`; product-specific exceptions stay in `.aifw/project-rules.yaml` and require the corresponding change lifecycle.
