import { BaseStageForm } from "@goauthentik/admin/stages/BaseStageForm";
import { DEFAULT_CONFIG } from "@goauthentik/common/api/config";
import "@goauthentik/elements/forms/HorizontalFormElement";
import "@goauthentik/elements/forms/FormGroup";

import { msg } from "@lit/localize";
import { TemplateResult, html } from "lit";
import { customElement } from "lit/decorators.js";
import { ifDefined } from "lit/directives/if-defined.js";

import { StagesApi, ExternalLogoutStage } from "@goauthentik/api";

@customElement("ak-stage-external-logout-form")
export class ExternalLogoutStageForm extends BaseStageForm<ExternalLogoutStage> {
    loadInstance(pk: string): Promise<ExternalLogoutStage> {
        return new StagesApi(DEFAULT_CONFIG).stagesExternalLogoutRetrieve({
            stageUuid: pk,
        });
    }

    async send(data: ExternalLogoutStage): Promise<ExternalLogoutStage> {
        if (this.instance) {
            return new StagesApi(DEFAULT_CONFIG).stagesExternalLogoutUpdate({
                stageUuid: this.instance.pk || "",
                externalLogoutStageRequest: data,
            });
        }
        return new StagesApi(DEFAULT_CONFIG).stagesExternalLogoutCreate({
            externalLogoutStageRequest: data,
        });
    }

    renderForm(): TemplateResult {
        return html`
            <ak-form-element-horizontal label=${msg("Name")} ?required=${true} name="name">
                <input
                    type="text"
                    value="${ifDefined(this.instance?.name || "")}"
                    class="pf-c-form-control"
                    required
                />
                <p class="pf-c-form__helper-text">
                    ${msg("Name of this stage.")}
                </p>
            </ak-form-element-horizontal>

            <ak-form-group .expanded=${true}>
                <span slot="header">
                    ${msg("Logout Configuration")}
                </span>
                <div slot="body" class="pf-c-form">
                    <ak-form-element-horizontal
                        label=${msg("Logout URL Template")}
                        name="logoutUrlTemplate"
                    >
                        <input
                            type="text"
                            value="${ifDefined(this.instance?.logoutUrlTemplate || "")}"
                            class="pf-c-form-control"
                            placeholder="https://example.com/logout?user={username}&client_id={client_id}"
                        />
                        <p class="pf-c-form__helper-text">
                            ${msg(
                                "URL template for external logout endpoint. Supports placeholders: {user_id}, {username}, {email}, {session_id}, {client_id}",
                            )}
                        </p>
                    </ak-form-element-horizontal>

                    <ak-form-element-horizontal label=${msg("HTTP Method")} name="httpMethod">
                        <select class="pf-c-form-control">
                            <option
                                value="POST"
                                ?selected=${this.instance?.httpMethod === "POST"}
                            >
                                POST
                            </option>
                            <option
                                value="GET"
                                ?selected=${this.instance?.httpMethod === "GET"}
                            >
                                GET
                            </option>
                            <option
                                value="DELETE"
                                ?selected=${this.instance?.httpMethod === "DELETE"}
                            >
                                DELETE
                            </option>
                        </select>
                        <p class="pf-c-form__helper-text">
                            ${msg("HTTP method to use for external logout requests")}
                        </p>
                    </ak-form-element-horizontal>

                    <ak-form-element-horizontal
                        label=${msg("Request Body Template")}
                        name="requestBodyTemplate"
                    >
                        <textarea
                            class="pf-c-form-control"
                            rows="4"
                            placeholder='{"username": "{username}", "session_id": "{session_id}"}'
                        >
${ifDefined(this.instance?.requestBodyTemplate || "")}</textarea
                        >
                        <p class="pf-c-form__helper-text">
                            ${msg(
                                "Template for request body (for POST requests). Supports same placeholders as URL template. Use JSON format for structured data.",
                            )}
                        </p>
                    </ak-form-element-horizontal>

                    <ak-form-element-horizontal
                        label=${msg("Additional Headers")}
                        name="additionalHeaders"
                    >
                        <textarea
                            class="pf-c-form-control"
                            rows="3"
                            placeholder='{"Authorization": "Bearer token", "X-Custom-Header": "value"}'
                        >
${ifDefined(this.instance?.additionalHeaders ? JSON.stringify(this.instance.additionalHeaders, null, 2) : "")}</textarea
                        >
                        <p class="pf-c-form__helper-text">
                            ${msg(
                                "Additional HTTP headers to send with logout requests (JSON format)",
                            )}
                        </p>
                    </ak-form-element-horizontal>

                    <ak-form-element-horizontal
                        label=${msg("Request Timeout")}
                        name="requestTimeout"
                    >
                        <input
                            type="number"
                            min="1"
                            max="300"
                            value="${ifDefined(this.instance?.requestTimeout || 10)}"
                            class="pf-c-form-control"
                        />
                        <p class="pf-c-form__helper-text">
                            ${msg("Timeout in seconds for external logout requests")}
                        </p>
                    </ak-form-element-horizontal>
                </div>
            </ak-form-group>

            <ak-form-group .expanded=${true}>
                <span slot="header">
                    ${msg("Logout Behavior")}
                </span>
                <div slot="body" class="pf-c-form">
                    <ak-form-element-horizontal name="globalLogout">
                        <label class="pf-c-switch">
                            <input
                                class="pf-c-switch__input"
                                type="checkbox"
                                ?checked=${ifDefined(this.instance?.globalLogout)}
                            />
                            <span class="pf-c-switch__toggle">
                                <span class="pf-c-switch__toggle-icon">
                                    <i class="fas fa-check" aria-hidden="true"></i>
                                </span>
                            </span>
                            <span class="pf-c-switch__label">${msg("Global Logout")}</span>
                        </label>
                        <p class="pf-c-form__helper-text">
                            ${msg(
                                "If enabled, will logout from all applications with active tokens. If disabled, only logs out from the current application.",
                            )}
                        </p>
                    </ak-form-element-horizontal>

                    <ak-form-element-horizontal name="revokeTokens">
                        <label class="pf-c-switch">
                            <input
                                class="pf-c-switch__input"
                                type="checkbox"
                                ?checked=${ifDefined(this.instance?.revokeTokens)}
                            />
                            <span class="pf-c-switch__toggle">
                                <span class="pf-c-switch__toggle-icon">
                                    <i class="fas fa-check" aria-hidden="true"></i>
                                </span>
                            </span>
                            <span class="pf-c-switch__label">${msg("Revoke OAuth Tokens")}</span>
                        </label>
                        <p class="pf-c-form__helper-text">
                            ${msg("Whether to revoke OAuth2 access and refresh tokens during logout")}
                        </p>
                    </ak-form-element-horizontal>

                    <ak-form-element-horizontal name="ignoreErrors">
                        <label class="pf-c-switch">
                            <input
                                class="pf-c-switch__input"
                                type="checkbox"
                                ?checked=${ifDefined(this.instance?.ignoreErrors)}
                            />
                            <span class="pf-c-switch__toggle">
                                <span class="pf-c-switch__toggle-icon">
                                    <i class="fas fa-check" aria-hidden="true"></i>
                                </span>
                            </span>
                            <span class="pf-c-switch__label">${msg("Ignore Errors")}</span>
                        </label>
                        <p class="pf-c-form__helper-text">
                            ${msg(
                                "If enabled, HTTP errors from external systems won't prevent the logout flow. If disabled, errors will be logged but the logout will continue.",
                            )}
                        </p>
                    </ak-form-element-horizontal>
                </div>
            </ak-form-group>
        `;
    }
}

declare global {
    interface HTMLElementTagNameMap {
        "ak-stage-external-logout-form": ExternalLogoutStageForm;
    }
}
