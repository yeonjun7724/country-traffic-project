import { createCn } from "cn/config";

/**
 * 클래스 병합. app/globals.css 의 글자 크기 단계(text-caption … text-display)를 font-size 그룹으로 등록한다 —
 * 등록하지 않으면 병합기가 이를 '글자 색'으로 보고 text-danger 같은 색 클래스와 겹칠 때 크기를 지운다.
 */
export const cn = createCn({
  extend: { classGroups: { "font-size": [{ text: ["caption", "small", "body", "title", "heading", "metric", "display"] }] } },
});
